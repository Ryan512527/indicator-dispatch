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
            from app.core.database import get_session
            async for session in get_session():
                try:
                    await analyze_card(card_type, session)
                    await session.commit()
                finally:
                    await session.close()
                break
        except Exception as e:
            logger.error(f"[AI分析失败] card_type={card_type}: {e}")

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


def _parse_analysis_response(content: str) -> dict:
    """从 LLM 返回内容中提取 JSON 结果。"""
    try:
        # 尝试直接解析
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个完整 JSON 对象
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"[AI分析] 无法解析 LLM 返回: {content[:500]}")
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
