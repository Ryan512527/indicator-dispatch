"""
AI Scheduler — 贾维斯式主动调度模块

数据更新 → 自动触发 LLM 分析 → 缓存结果 → 紧急事项 WxPusher 推送
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func as _func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import chat_completion, is_llm_available
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 后台分析任务跟踪 ──
_pending_tasks: dict[str, asyncio.Task] = {}


def _is_running() -> None:
    """环境哨兵 — 非 asyncio 环境会直接报错。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError("AI Scheduler 必须在 asyncio 事件循环中运行")


def _build_version_fingerprint(data: dict) -> str:
    """基于数据内容生成指纹（用于判断是否需要重新分析）。"""
    import hashlib
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def trigger_ai_analysis(card_type: str, db: AsyncSession) -> None:
    """
    每次 reparse 完成后调用此函数，在后台异步触发 AI 分析。
    不阻塞主流程，失败也不影响 reparse 结果。
    """
    _is_running()

    async def _do_analyze():
        try:
            # 创建独立的数据库会话（避免污染 reparse 的事务）
            from app.core.database import async_session
            async with async_session() as session:
                await analyze_card(card_type, session)
                await session.commit()
        except Exception as e:
            logger.error(f"[AI分析失败] card_type={card_type}: {e}", exc_info=True)

    # 取消同类型正在进行的分析（避免重复）
    if card_type in _pending_tasks and not _pending_tasks[card_type].done():
        _pending_tasks[card_type].cancel()

    task = asyncio.create_task(_do_analyze())
    _pending_tasks[card_type] = task
    logger.info(f"[AI分析] 已触发后台分析 card_type={card_type}")


async def analyze_card(card_type: str, db: AsyncSession) -> dict:
    """根据 card_type 分发到对应的分析函数。"""
    if not is_llm_available():
        logger.warning("[AI分析] LLM 未配置，跳过分析")
        return {"status": "skipped", "reason": "LLM 未配置"}

    analysis_map = {
        "complaint_2200000": _analyze_complaint_2200000,
        "daily-report": _analyze_daily_report,
        "city-workload": _analyze_city_workload,
        "offline-dispatch": _analyze_offline_dispatch,
    }

    handler = analysis_map.get(card_type)
    if not handler:
        logger.warning(f"[AI分析] card_type={card_type} 暂无分析逻辑")
        return {"status": "skipped", "reason": f"card_type={card_type} 暂不支持"}

    return await handler(db)


# ═══════════════════════════════════════════
# 具体指标分析函数
# ═══════════════════════════════════════════

async def _analyze_complaint_2200000(db: AsyncSession) -> dict:
    """分析 2200000投诉积压清单，生成重要事项清单。"""
    from app.core.models import Complaint2200000Detail, AIAnalysisCache

    # 1. 拉取明细数据
    stmt = select(Complaint2200000Detail).order_by(Complaint2200000Detail.id.desc()).limit(200)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return {"status": "no_data"}

    # 2. 提取关键字段（最多 50 条，避免 token 爆炸）
    records = []
    for row in rows[:50]:
        records.append({
            "id": row.id,
            "宽带账号": row.broadband_account,
            "超时时限": row.timeout_deadline,
            "是否重要客户": row.is_important_customer,
            "客户联系方式": row.customer_contact,
            "施工地址": row.construction_address,
            "处理人": row.handler_name,
            "分类": row.category,
        })

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 3. 组装提示词
    prompt = _build_2200000_prompt(records, now_str)

    # 4. 调用 LLM
    try:
        llm_response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"[AI分析] LLM 调用失败: {e}")
        return {"status": "llm_error", "error": str(e)}

    # 5. 解析结果
    parsed = _parse_analysis_response(content)

    # 6. 写入缓存
    fingerprint = _build_version_fingerprint({"card_type": "complaint_2200000", "records": records})
    existing = await db.execute(
        select(AIAnalysisCache).where(
            AIAnalysisCache.card_type == "complaint_2200000",
            AIAnalysisCache.analysis_version == fingerprint,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("[AI分析] 数据未变化，跳过写入缓存")
        return {"status": "cached", "fingerprint": fingerprint}

    cache = AIAnalysisCache(
        card_type="complaint_2200000",
        report_file_id=rows[0].report_file_id if rows else None,
        analysis_version=fingerprint,
        todos=parsed.get("todos", []),
        summary=parsed.get("summary", ""),
        risk_level=parsed.get("risk_level", "低"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(cache)
    await db.flush()

    # 7. 高优先级事项 → 触发 WxPusher 推送
    await _maybe_push_to_wxpusher(
        card_type="complaint_2200000",
        card_label="2200000投诉积压",
        todos=parsed.get("todos", []),
        risk_level=parsed.get("risk_level", "低"),
        cache_id=cache.id,
    )

    logger.info(
        f"[AI分析] complaint_2200000 完成, "
        f"risk={cache.risk_level}, todos={len(cache.todos)}, pushed={cache.pushed}"
    )
    return {"status": "done", "todos_count": len(cache.todos), "risk_level": cache.risk_level}


def _build_2200000_prompt(records: list[dict], now_str: str) -> str:
    """构建 2200000 投诉积压的分析提示词。"""
    data_json = json.dumps(records, ensure_ascii=False, indent=2)

    return f"""你是"指标调度平台"的AI调度助手，代号贾维斯。

以下是【2200000投诉积压清单】横山地区的最新明细数据（共{len(records)}条，当前时间 {now_str}）：

{data_json}

请扮演运维调度专家，完成分析并以**严格JSON**输出（不要输出markdown代码块标记，直接输出JSON对象）：

{{
  "risk_level": "高/中/低",
  "summary": "1-2句话的整体情况描述（中文）",
  "todos": [
    {{
      "priority": "高/中/低",
      "title": "简短标题（15字内）",
      "description": "详细说明，含具体账号/地址/处理人信息",
      "assignee": "建议处理人姓名",
      "deadline": "超时时间或建议处理时限",
      "record_ids": [123, 456]
    }}
  ]
}}

分析重点（按优先级排序）：
1. 即将超时（24h内）→ 高优先级，必须包含超时时限
2. 重要客户（"是否重要客户"="是"）→ 中优先级
3. 同一施工地址多次出现 → 中优先级，说明地址聚集
4. 分类为"在途"的 → 中优先级，需持续关注
5. assignee 优先填处理人字段的值，若无则填"待分配"
6. title 要简洁且可操作，description 要包含具体细节

注意：
- todos 按优先级从高到低排序
- 最多输出 10 条 todos
- 如果某类没有，就不用列出
- 只输出 JSON，不要任何额外文字"""


# ═══════════════════════════════════════════
# 日报（daily-report）分析
# ═══════════════════════════════════════════

async def _analyze_daily_report(db: AsyncSession) -> dict:
    """分析日报 — 两类/五类装机成功率 + 积压清单，生成重点关注事项。"""
    from app.core.models import DailyReportSummary, DailyReportBacklog, AIAnalysisCache

    # 汇总数据
    stmt_sum = select(DailyReportSummary).order_by(DailyReportSummary.id.desc()).limit(1)
    result = await db.execute(stmt_sum)
    summary = result.scalar_one_or_none()

    # 积压明细（取积压超过 24h 的，最多 50 条）
    stmt_log = (
        select(DailyReportBacklog)
        .order_by(DailyReportBacklog.id.desc())
        .limit(200)
    )
    log_result = await db.execute(stmt_log)
    all_rows = log_result.scalars().all()
    # 只取积压时长 > 24h 的
    backlog_rows = []
    for row in all_rows:
        try:
            bh = float(row.backlog_hours or "0")
        except (ValueError, TypeError):
            bh = 0
        if bh > 24:
            backlog_rows.append(row)

    if not summary and not backlog_rows:
        return {"status": "no_data"}

    records = []
    for row in backlog_rows[:15]:
        records.append({
            "id": row.id,
            "宽带账号": row.account,
            "施工地址": row.address,
            "施工人": row.worker_name,
            "积压时长h": row.backlog_hours,
            "完成时限": row.deadline,
            "用户品牌": row.user_brand,
            "数据来源": row.data_source,
        })

    summary_data = None
    if summary:
        summary_data = {
            "日期": summary.report_date,
            "两类_积压总量": summary.two_cat_backlog_total,
            "两类_家宽转化率": summary.two_cat_broadband_rate,
            "两类_FTTR转化率": summary.two_cat_fttr_rate,
            "两类_总装机转化率": summary.two_cat_total_rate,
            "五类_积压总量": summary.five_cat_backlog_total,
            "五类_家宽转化率": summary.five_cat_broadband_rate,
            "五类_智能组网": summary.five_cat_smart_network,
            "五类_平安乡村": summary.five_cat_safe_village,
            "五类_FTTR转化率": summary.five_cat_fttr_rate,
            "五类_总装机转化率": summary.five_cat_total_rate,
        }

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt = _build_daily_report_prompt(summary_data, records, now_str)

    try:
        llm_response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8192,
        )
        content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"[AI分析] 日报 LLM 调用失败: {e}")
        return {"status": "llm_error", "error": str(e)}

    parsed = _parse_analysis_response(content)

    fingerprint = _build_version_fingerprint({"card_type": "daily-report", "records": records, "summary": summary_data})

    existing = await db.execute(
        select(AIAnalysisCache).where(
            AIAnalysisCache.card_type == "daily-report",
            AIAnalysisCache.analysis_version == fingerprint,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("[AI分析] 日报数据未变化，跳过写入缓存")
        return {"status": "cached", "fingerprint": fingerprint}

    cache = AIAnalysisCache(
        card_type="daily-report",
        report_file_id=backlog_rows[0].report_file_id if backlog_rows else None,
        analysis_version=fingerprint,
        todos=parsed.get("todos", []),
        summary=parsed.get("summary", ""),
        risk_level=parsed.get("risk_level", "低"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(cache)
    await db.flush()

    await _maybe_push_to_wxpusher(
        card_type="daily-report",
        card_label="日报·装机成功率",
        todos=parsed.get("todos", []),
        risk_level=parsed.get("risk_level", "低"),
        cache_id=cache.id,
    )

    logger.info(f"[AI分析] daily-report 完成, risk={cache.risk_level}, todos={len(cache.todos)}")
    return {"status": "done", "todos_count": len(cache.todos), "risk_level": cache.risk_level}


def _build_daily_report_prompt(summary_data: dict | None, records: list[dict], now_str: str) -> str:
    data_json = json.dumps({"汇总指标": summary_data, "积压超过24h工单": records}, ensure_ascii=False, indent=2)

    return f"""你是"指标调度平台"的AI调度助手，代号贾维斯。

以下是横山地区【日报·装机成功率】最新数据（当前时间 {now_str}）：

{data_json}

请扮演运维调度专家，完成分析并以**严格JSON**输出（不要输出markdown代码块标记，直接输出JSON对象）：

{{
  "risk_level": "高/中/低",
  "summary": "1-2句话的整体情况描述（中文，含转化率趋势判断）",
  "todos": [
    {{
      "priority": "高/中/低",
      "title": "简短标题（15字内）",
      "description": "详细说明，含具体账号/地址/施工人信息",
      "assignee": "建议处理人姓名",
      "deadline": "完成时限或建议处理时限",
      "record_ids": [123, 456]
    }}
  ]
}}

分析重点（按优先级排序）：
1. 转化率异常：任何转化率低于同类均值的类别 → 高优先级
2. 积压超过48h的工单 → 高优先级，必须列出施工人+地址
3. 同一施工人多次出现 → 中优先级
4. FTTR转化率低于家宽转化率 → 中优先级
5. assignee 优先填施工人字段的值，若无则填"待分配"

注意：
- todos 按优先级从高到低排序
- 最多输出 8 条 todos
- description 控制在80字以内
- 只输出 JSON，不要任何额外文字"""


# ═══════════════════════════════════════════
# 全市装维工作量统计（city-workload）分析
# ═══════════════════════════════════════════

async def _analyze_city_workload(db: AsyncSession) -> dict:
    """分析装维工作量 — 人员出勤 + 积压分布，发现风险人员/网格。"""
    from app.core.models import CityWorkloadSummary, CityWorkloadWorker, AIAnalysisCache

    stmt_sum = select(CityWorkloadSummary).order_by(CityWorkloadSummary.id.desc()).limit(1)
    result = await db.execute(stmt_sum)
    summary = result.scalar_one_or_none()

    stmt_w = select(CityWorkloadWorker).order_by(CityWorkloadWorker.id.desc()).limit(200)
    w_result = await db.execute(stmt_w)
    workers = w_result.scalars().all()

    if not summary and not workers:
        return {"status": "no_data"}

    # 提取高积压人员（核心积压=装移拆+投诉+巡检，排除LAN）
    high_backlog = []
    for w in workers:
        wl = w.workload or {}
        # 计算核心积压（装移拆 + 投诉 + 巡检），LAN不参与优先级判断
        core_backlog = 0
        for key in ("装移拆", "投诉", "巡检"):
            if key in wl and isinstance(wl[key], dict):
                core_backlog += int(wl[key].get("backlog", 0) or 0)
        # LAN积压单独记录供参考
        lan_backlog = 0
        if "LAN" in wl and isinstance(wl["LAN"], dict):
            lan_backlog = int(wl["LAN"].get("backlog", 0) or 0)
        # 以核心积压为准判断是否高积压（>3即纳入分析）
        if core_backlog > 3:
            high_backlog.append({
                "姓名": w.worker_name,
                "区域": w.area,
                "网格": w.grid,
                "核心积压总量": core_backlog,
                "LAN积压(仅供参考)": lan_backlog,
                "积压总量": w.total_backlog,
                "当日工作量": w.total_today,
                "工作类型明细": wl,
            })

    high_backlog.sort(key=lambda x: x["核心积压总量"], reverse=True)

    summary_data = None
    if summary:
        summary_data = {
            "日期": summary.report_date,
            "人员数量": summary.total_staff,
            "有工作量人数": summary.working_staff,
            "请假人数": summary.leave_staff,
            "无工作量占比": summary.no_work_ratio,
        }

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt = _build_workload_prompt(summary_data, high_backlog[:15], now_str)

    try:
        llm_response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8192,
        )
        content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"[AI分析] 装维工作量 LLM 调用失败: {e}")
        return {"status": "llm_error", "error": str(e)}

    parsed = _parse_analysis_response(content)

    fingerprint = _build_version_fingerprint({
        "card_type": "city-workload",
        "summary": summary_data,
        "high_backlog": [w["姓名"] for w in high_backlog[:15]],
        "version": 2,  # v2: 核心积压（装移拆+投诉+巡检），排除LAN
    })

    existing = await db.execute(
        select(AIAnalysisCache).where(
            AIAnalysisCache.card_type == "city-workload",
            AIAnalysisCache.analysis_version == fingerprint,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("[AI分析] 装维工作量数据未变化，跳过写入缓存")
        return {"status": "cached", "fingerprint": fingerprint}

    cache = AIAnalysisCache(
        card_type="city-workload",
        report_file_id=None,
        analysis_version=fingerprint,
        todos=parsed.get("todos", []),
        summary=parsed.get("summary", ""),
        risk_level=parsed.get("risk_level", "低"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(cache)
    await db.flush()

    await _maybe_push_to_wxpusher(
        card_type="city-workload",
        card_label="装维工作量",
        todos=parsed.get("todos", []),
        risk_level=parsed.get("risk_level", "低"),
        cache_id=cache.id,
    )

    logger.info(f"[AI分析] city-workload 完成, risk={cache.risk_level}, todos={len(cache.todos)}")
    return {"status": "done", "todos_count": len(cache.todos), "risk_level": cache.risk_level}


def _build_workload_prompt(summary_data: dict | None, high_backlog: list[dict], now_str: str) -> str:
    data_json = json.dumps({"汇总": summary_data, "高积压人员(核心积压>3件)": high_backlog}, ensure_ascii=False, indent=2)

    return f"""你是"指标调度平台"的AI调度助手，代号贾维斯。

以下是横山地区【全市装维工作量统计】最新数据（当前时间 {now_str}）：

{data_json}

说明：核心积压总量 = 装移拆积压 + 投诉积压 + 巡检积压，**不含LAN**。
LAN积压数量级大（通常几十到上百件），属于批量维护类工单，单独列出仅供参考，**不参与低中高优先级判断**。

请扮演运维调度专家，完成分析并以**严格JSON**输出（不要输出markdown代码块标记，直接输出JSON对象）：

{{
  "risk_level": "高/中/低",
  "summary": "1-2句话的整体情况描述（中文），重点关注装移拆/投诉/巡检三项核心指标",
  "todos": [
    {{
      "priority": "高/中/低",
      "title": "简短标题（15字内）",
      "description": "详细说明，含具体人员姓名/积压量（区分核心积压和LAN积压）/区域信息",
      "assignee": "建议处理人姓名（网格长或直接负责人）",
      "deadline": "建议处理时限",
      "record_ids": []
    }}
  ]
}}

分析重点（**按核心积压判断优先级，LAN数据不参与优先级计算**）：
1. 无工作量占比过高（>20%） → 高优先级，需分析人员分布
2. 单个装维人员**核心积压**（装移拆+投诉+巡检） > 8件 → 高优先级，需调度支援
3. 同一人员**核心积压** 5-8件 → 中优先级
4. 请假人数异常（>5人） → 中优先级
5. 同一网格多人**核心积压**超标 → 中优先级，说明网格整体压力大
6. 当日核心工作量为0且核心积压 > 3 → 中优先级

注意：
- 优先级仅基于装移拆、投诉、巡检三项核心积压判断
- LAN积压数据可在 description 中提及作为参考，但**不能作为提级理由**
- todos 按优先级从高到低排序
- 最多输出 8 条 todos
- assignee 优先填网格长或直接负责人，若无则填"待分配"
- 只输出 JSON，不要任何额外文字"""



# ═══════════════════════════════════════════
# 线下派单处理情况（offline-dispatch）分析
# ═══════════════════════════════════════════

async def _analyze_offline_dispatch(db: AsyncSession) -> dict:
    """分析线下派单处理情况 — 超时积压 + VIP客户 + 在途工单。"""
    from app.core.models import OfflineDispatchSummary, OfflineDispatchDetail, AIAnalysisCache

    stmt_sum = select(OfflineDispatchSummary).order_by(OfflineDispatchSummary.id.desc()).limit(1)
    result = await db.execute(stmt_sum)
    summary = result.scalar_one_or_none()

    stmt_d = select(OfflineDispatchDetail).order_by(OfflineDispatchDetail.id.desc()).limit(200)
    d_result = await db.execute(stmt_d)
    details = d_result.scalars().all()

    if not summary and not details:
        return {"status": "no_data"}

    records = []
    for row in details[:50]:
        records.append({
            "id": row.id,
            "宽带账号": row.broadband_account,
            "超时时限": row.timeout_limit,
            "是否VIP客户": row.is_vip_customer,
            "客户联系方式": row.customer_contact,
            "施工地址": row.construction_address,
            "处理人": row.handler_name,
            "分类": row.category,
            "工单号": row.order_no,
        })

    summary_data = None
    if summary:
        summary_data = {
            "日期": summary.report_date,
            "月派单量": summary.monthly_dispatch,
            "超时积压24h": summary.overdue_backlog,
            "未超时积压24h": summary.not_overdue_backlog,
            "累计在途": summary.total_in_transit,
            "预警4h超时": summary.warn_4h_overdue,
        }

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt = _build_offline_dispatch_prompt(summary_data, records, now_str)

    try:
        llm_response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8192,
        )
        content = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"[AI分析] 线下派单 LLM 调用失败: {e}")
        return {"status": "llm_error", "error": str(e)}

    parsed = _parse_analysis_response(content)

    fingerprint = _build_version_fingerprint({"card_type": "offline-dispatch", "records": records})

    existing = await db.execute(
        select(AIAnalysisCache).where(
            AIAnalysisCache.card_type == "offline-dispatch",
            AIAnalysisCache.analysis_version == fingerprint,
        )
    )
    if existing.scalar_one_or_none():
        logger.info("[AI分析] 线下派单数据未变化，跳过写入缓存")
        return {"status": "cached", "fingerprint": fingerprint}

    cache = AIAnalysisCache(
        card_type="offline-dispatch",
        report_file_id=details[0].report_file_id if details else None,
        analysis_version=fingerprint,
        todos=parsed.get("todos", []),
        summary=parsed.get("summary", ""),
        risk_level=parsed.get("risk_level", "低"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(cache)
    await db.flush()

    await _maybe_push_to_wxpusher(
        card_type="offline-dispatch",
        card_label="线下派单",
        todos=parsed.get("todos", []),
        risk_level=parsed.get("risk_level", "低"),
        cache_id=cache.id,
    )

    logger.info(f"[AI分析] offline-dispatch 完成, risk={cache.risk_level}, todos={len(cache.todos)}")
    return {"status": "done", "todos_count": len(cache.todos), "risk_level": cache.risk_level}


def _build_offline_dispatch_prompt(summary_data: dict | None, records: list[dict], now_str: str) -> str:
    data_json = json.dumps({"汇总指标": summary_data, "工单明细": records}, ensure_ascii=False, indent=2)

    return f"""你是"指标调度平台"的AI调度助手，代号贾维斯。

以下是横山地区【线下派单处理情况】最新数据（当前时间 {now_str}）：

{data_json}

请扮演运维调度专家，完成分析并以**严格JSON**输出（不要输出markdown代码块标记，直接输出JSON对象）：

{{
  "risk_level": "高/中/低",
  "summary": "1-2句话的整体情况描述（中文）",
  "todos": [
    {{
      "priority": "高/中/低",
      "title": "简短标题（15字内）",
      "description": "详细说明，含具体账号/地址/处理人信息",
      "assignee": "建议处理人姓名",
      "deadline": "超时时间或建议处理时限",
      "record_ids": [123, 456]
    }}
  ]
}}

分析重点（按优先级排序）：
1. 预警4h超时数量 > 0 → 高优先级，必须立即处理
2. VIP客户（"是否VIP客户"="是"）→ 高优先级
3. 超时积压24h > 0 → 中优先级，需尽快处理
4. 分类为"在途"的超时工单 → 中优先级
5. 同一处理人多次出现 → 中优先级
6. assignee 优先填处理人字段的值，若无则填"待分配"

注意：
- todos 按优先级从高到低排序
- 最多输出 10 条 todos
- 只输出 JSON，不要任何额外文字"""


def _parse_analysis_response(content: str) -> dict:
    """从 LLM 返回内容中提取 JSON 结果。使用平衡括号匹配，可处理前后有额外文本的情况。"""
    # 1. 尝试直接解析整个文本
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. 尝试提取 ```json ... ``` 或 ``` ... ``` 块
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 用平衡括号算法找到第一个完整的 JSON 对象
    brace_count = 0
    start = -1
    for i, ch in enumerate(content):
        if ch == '{':
            if brace_count == 0:
                start = i
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0 and start >= 0:
                try:
                    return json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    # 这个括号块不是有效JSON，继续找下一个
                    start = -1

    # 4. 最后尝试：用贪婪匹配取首个{到末个}（部分场景兜底）
    first_brace = content.find('{')
    last_brace = content.rfind('}')
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(content[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"[AI分析] 无法解析 LLM 返回 (前500字符): {content[:500]}")
    return {"todos": [], "summary": content, "risk_level": "低"}


# ═══════════════════════════════════════════
# WxPusher 推送
# ═══════════════════════════════════════════

async def _maybe_push_to_wxpusher(
    card_type: str,
    card_label: str,
    todos: list[dict],
    risk_level: str,
    cache_id: int,
) -> None:
    """当 risk_level=高 或有 priority=高 的 todo 时，推送 WxPusher 消息。"""
    high_todos = [t for t in todos if t.get("priority") == "高"]
    if risk_level != "高" and not high_todos:
        logger.info("[AI推送] 无紧急事项，跳过 WxPusher 推送")
        return

    # 检查 WxPusher 是否已配置
    if not settings.wxpusher_app_token:
        logger.warning("[AI推送] WxPusher 未配置，跳过推送")
        return

    try:
        from app.notifier.service import notifier

        # 构建推送内容
        lines = [
            f"🚨 <b>指标调度紧急提醒</b>",
            f"",
            f"【{card_label}】风险等级：<b>{risk_level}</b>",
            f"发现 <b>{len(high_todos)}</b> 项需紧急处理：",
            f"",
        ]
        for i, todo in enumerate(high_todos[:5], 1):
            lines.append(f"{i}. <b>{todo.get('title', '')}</b>")
            lines.append(f"   {todo.get('description', '')}")
            lines.append(f"   处理人: {todo.get('assignee', '待分配')}  ·  时限: {todo.get('deadline', '')}")
            lines.append("")

        lines.append("── 贾维斯 · 指标调度平台")

        content = "\n".join(lines)

        success = await notifier.send_message(
            content=content,
            summary=f"[{card_label}] {len(high_todos)}项紧急事项",
        )

        if success:
            logger.info(f"[AI推送] WxPusher 推送成功, card_type={card_type}, high_todos={len(high_todos)}")
            # 更新缓存记录的 pushed 状态
            from app.core.models import AIAnalysisCache
            from sqlalchemy import update

            await db.execute(
                update(AIAnalysisCache)
                .where(AIAnalysisCache.id == cache_id)
                .values(pushed=True, push_time=datetime.now(timezone.utc))
            )
        else:
            logger.warning("[AI推送] WxPusher 推送返回失败")

    except Exception as e:
        logger.error(f"[AI推送] WxPusher 推送异常: {e}")


# ═══════════════════════════════════════════
# 缓存查询（供 API 使用）
# ═══════════════════════════════════════════

async def get_analysis_cache(
    db: AsyncSession,
    card_type: str,
    force_refresh: bool = False,
) -> dict:
    """获取分析缓存。如果 force_refresh=True 则重新分析。"""
    from app.core.models import AIAnalysisCache

    if force_refresh:
        logger.info(f"[AI分析] 强制刷新 card_type={card_type}")
        await analyze_card(card_type, db)
        await db.commit()  # 持久化分析结果

    # 查询最新缓存
    stmt = (
        select(AIAnalysisCache)
        .where(AIAnalysisCache.card_type == card_type)
        .order_by(AIAnalysisCache.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        return {"status": "empty", "card_type": card_type, "todos": [], "summary": ""}

    return {
        "status": "ok",
        "card_type": row.card_type,
        "todos": row.todos or [],
        "summary": row.summary or "",
        "risk_level": row.risk_level or "低",
        "pushed": row.pushed,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "analysis_version": row.analysis_version,
    }
