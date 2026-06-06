from fastapi import APIRouter, Depends, Query
import os
import fnmatch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.core.database import get_db
from app.core.config import settings
from app.core.models import IndicatorDefinition, IndicatorEvent

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


# ── Indicators ──

@router.get("/indicators")
async def list_indicators(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IndicatorDefinition).order_by(IndicatorDefinition.created_at.desc())
    if category:
        stmt = stmt.where(IndicatorDefinition.category == category)
    if search:
        stmt = stmt.where(
            IndicatorDefinition.name.ilike(f"%{search}%")
            | IndicatorDefinition.code.ilike(f"%{search}%")
        )
    result = await db.execute(stmt)
    return [row.to_dict() if hasattr(row, "to_dict") else {
        "id": str(row.id),
        "name": row.name,
        "code": row.code,
        "category": row.category,
        "unit": row.unit,
        "tags": row.tags,
        "created_at": row.created_at.isoformat(),
    } for row in result.scalars()]


@router.get("/indicators/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IndicatorDefinition.category)
        .where(IndicatorDefinition.category.isnot(None))
        .distinct()
        .order_by(IndicatorDefinition.category)
    )
    return [row[0] for row in result.all()]


# ── Events (Indicator Data) ──

@router.get("/events")
async def query_events(
    indicator_id: Optional[str] = None,
    category: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    dimensions: Optional[str] = Query(None, description="JSON filter for dimensions"),
    limit: int = Query(1000, le=10000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if indicator_id:
        conditions.append(IndicatorEvent.indicator_id == indicator_id)

    if category:
        subq = select(IndicatorDefinition.id).where(IndicatorDefinition.category == category)
        conditions.append(IndicatorEvent.indicator_id.in_(subq))

    if start:
        conditions.append(IndicatorEvent.time >= datetime.fromisoformat(start))
    if end:
        conditions.append(IndicatorEvent.time <= datetime.fromisoformat(end))

    stmt = (
        select(IndicatorEvent)
        .order_by(IndicatorEvent.time.desc())
        .limit(limit)
        .offset(offset)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [{
        "id": str(r.id),
        "time": r.time.isoformat(),
        "indicator_id": str(r.indicator_id),
        "indicator_name": r.indicator.name if r.indicator else None,
        "value": r.value,
        "source": r.source,
        "dimensions": r.dimensions or {},
    } for r in rows]


@router.get("/events/aggregate")
async def aggregate_events(
    group_by: str = Query("time", description="time_window, indicator_id, or dimension key"),
    time_bucket: str = Query("1 day", description="e.g. 1 hour, 1 day, 7 days"),
    aggregation: str = Query("avg", description="avg, sum, max, min, count"),
    indicator_id: Optional[str] = None,
    category: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if group_by == "time_window":
        bucket_unit = time_bucket.split()[-1] if " " in time_bucket else time_bucket
        group_col = func.date_trunc(bucket_unit, IndicatorEvent.time).label("bucket")
    elif group_by == "indicator_id":
        group_col = IndicatorEvent.indicator_id.label("bucket")
    else:
        group_col = IndicatorEvent.dimensions[group_by].astext.label("bucket")

    agg_funcs = {"avg": func.avg, "sum": func.sum, "max": func.max, "min": func.min, "count": func.count}
    agg_fn = agg_funcs.get(aggregation, func.avg)

    stmt = select(group_col, agg_fn(IndicatorEvent.value).label("value"))
    conditions = []

    if indicator_id:
        conditions.append(IndicatorEvent.indicator_id == indicator_id)
    if category:
        subq = select(IndicatorDefinition.id).where(IndicatorDefinition.category == category)
        conditions.append(IndicatorEvent.indicator_id.in_(subq))
    if start:
        conditions.append(IndicatorEvent.time >= datetime.fromisoformat(start))
    if end:
        conditions.append(IndicatorEvent.time <= datetime.fromisoformat(end))

    if conditions:
        stmt = stmt.where(*conditions)
    stmt = stmt.group_by(group_col).order_by(group_col)

    result = await db.execute(stmt)
    rows = result.all()
    return [{
        "bucket": str(r[0]) if hasattr(r[0], "isoformat") else r[0],
        "value": round(float(r[1]), 4) if r[1] is not None else None,
    } for r in rows]


# ── AI Chat ──

@router.post("/ai/chat")
async def ai_chat(
    message: str,
    db: AsyncSession = Depends(get_db),
):
    from app.ai.service import ai_chat_handler
    return await ai_chat_handler(message, db)


# ── File sources (for latest file detection) ──

@router.get("/sources")
async def list_sources(
    pattern: str = Query(""),
    limit: int = Query(10),
):
    """List files in the watch directory, sorted by modification time (newest first)."""
    watch_dir = settings.watch_dir
    if not watch_dir:
        return {"files": []}

    matching = []
    for root, dirs, files in os.walk(watch_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if pattern and not fnmatch.fnmatch(f, f"*{pattern}*"):
                continue
            fpath = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(fpath)
                matching.append({
                    "name": f,
                    "path": fpath,
                    "mtime": datetime.fromtimestamp(mtime).isoformat(),
                    "size": os.path.getsize(fpath),
                })
            except OSError:
                pass

    matching.sort(key=lambda x: x["mtime"], reverse=True)
    return {"files": matching[:limit]}


# ── Report Data (recurring report parser) ──

@router.post("/reports/scan")
async def scan_reports(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    扫描监听目录，识别出现≥3次的报表类型，
    注册到 report_types 表。
    """
    from app.services.report_scanner import scan_and_register
    if directory is None:
        from app.core.config import settings
        directory = settings.watch_dir
    result = await scan_and_register(directory, db)
    return {"scanned": len(result), "results": result}


@router.post("/reports/parse-all")
async def parse_all_reports(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    解析所有已注册的报表类型（逐个调用 parse_report_type）。
    返回每个类型的解析结果。
    """
    from app.services.report_scanner import (
        parse_report_type,
        get_report_types,
    )
    if directory is None:
        from app.core.config import settings
        directory = settings.watch_dir

    types = await get_report_types(db)
    results = []
    for rt in types:
        r = await parse_report_type(rt["name"], db, directory)
        results.append({"name": rt["name"], **r})
    return {"total_types": len(types), "results": results}


@router.post("/reports/parse")
async def parse_one_report(
    report_type: str = Query(..., description="报表类型名称，如：无线退服清单"),
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """解析指定报表类型的所有文件，入库。"""
    from app.services.report_scanner import parse_report_type
    result = await parse_report_type(report_type, db, directory)
    return {"report_type": report_type, **result}


@router.get("/reports/types")
async def list_report_types(
    db: AsyncSession = Depends(get_db),
):
    """获取所有报表类型及统计信息。"""
    from app.services.report_scanner import get_report_types
    return await get_report_types(db)


@router.get("/reports/types/{type_id}/records")
async def get_report_type_records(
    type_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取某报表类型的记录。"""
    from app.services.report_scanner import get_report_records
    return await get_report_records(type_id, db, page, page_size)


# ── 无线退服横山专用 API ──

@router.get("/reports/wireless-outage/summary")
async def wireless_outage_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取无线退服横山数据概要：退服总数 + 告警名称列表"""
    from app.services.report_scanner import get_wireless_outage_summary
    return await get_wireless_outage_summary(db)


@router.get("/reports/wireless-outage/detail")
async def wireless_outage_detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取无线退服横山详细数据（仅9个字段）"""
    from app.services.report_scanner import get_wireless_outage_detail
    return await get_wireless_outage_detail(db, page, page_size)


@router.get("/reports/wireless-outage/trend")
async def wireless_outage_trend(
    hours: int = Query(48, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """获取最近 N 小时无线退服横山数量趋势"""
    from app.services.report_scanner import get_wireless_outage_trend
    return await get_wireless_outage_trend(db, hours)


@router.post("/reports/wireless-outage/reparse")
async def wireless_outage_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析无线退服清单文件，仅保留横山区9个字段"""
    from app.services.report_scanner import reparse_wireless_outage
    result = await reparse_wireless_outage(db, directory)
    return {"report_type": "无线退服清单", **result}


# ── 皮站故障横山专用 API ──

@router.get("/reports/pisite-fault/summary")
async def pisite_fault_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取皮站故障横山数据概要：故障总数 + 设备厂商列表"""
    from app.services.report_scanner import get_pisite_fault_summary
    return await get_pisite_fault_summary(db)


@router.get("/reports/pisite-fault/detail")
async def pisite_fault_detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取皮站故障横山详细数据（仅5个字段）"""
    from app.services.report_scanner import get_pisite_fault_detail
    return await get_pisite_fault_detail(db, page, page_size)


# ── 接入层通报横山专用 API ──

@router.get("/reports/access-layer/summary")
async def access_layer_fault_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取接入层通报横山数据概要：故障总数 + 影响业务数 + 不影响业务数 + 告警码名称列表"""
    from app.services.report_scanner import get_access_layer_fault_summary
    return await get_access_layer_fault_summary(db)


@router.get("/reports/access-layer/detail")
async def access_layer_fault_detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取接入层通报横山详细数据（仅6个字段）"""
    from app.services.report_scanner import get_access_layer_fault_detail
    return await get_access_layer_fault_detail(db, page, page_size)


@router.post("/reports/access-layer/reparse")
async def access_layer_fault_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析接入层通报文件，仅保留横山区6个字段"""
    from app.services.report_scanner import reparse_access_layer_fault
    result = await reparse_access_layer_fault(db, directory)
    return {"report_type": "接入层通报", **result}


@router.post("/reports/pisite-fault/reparse")
async def pisite_fault_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析皮站故障清单文件，仅保留横山区5个字段"""
    from app.services.report_scanner import reparse_pisite_fault
    result = await reparse_pisite_fault(db, directory)
    return {"report_type": "皮站故障清单", **result}


# ── 企宽装机通报横山专用 API ──

@router.get("/reports/enterprise-broadband/summary")
async def enterprise_broadband_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取企宽装机通报横山卡片汇总指标（10个字段）"""
    from app.services.report_scanner import get_enterprise_broadband_summary
    return await get_enterprise_broadband_summary(db)


@router.get("/reports/enterprise-broadband/backlog")
async def enterprise_broadband_backlog(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取企宽装机通报横山积压清单"""
    from app.services.report_scanner import get_enterprise_broadband_backlog
    return await get_enterprise_broadband_backlog(db, page, page_size)


@router.post("/reports/enterprise-broadband/reparse")
async def enterprise_broadband_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析企宽装机通报文件，提取横山汇总指标和积压清单"""
    from app.services.report_scanner import reparse_enterprise_broadband
    result = await reparse_enterprise_broadband(db, directory)
    return {"report_type": "企宽装机通报", **result}


# ── 日报横山专用 API ──

@router.get("/reports/daily-report/summary")
async def daily_report_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取日报横山卡片汇总指标（两类+五类装机成功率）"""
    from app.services.report_scanner import get_daily_report_summary
    return await get_daily_report_summary(db)


@router.get("/reports/daily-report/backlog")
async def daily_report_backlog(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取日报横山装机积压清单（含装机历时计算和时长提醒）"""
    from app.services.report_scanner import get_daily_report_backlog
    return await get_daily_report_backlog(db, page, page_size)


@router.post("/reports/daily-report/reparse")
async def daily_report_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析日报文件，提取横山两类/五类概况 + 宽带积压清单"""
    from app.services.report_scanner import reparse_daily_report
    result = await reparse_daily_report(db, directory)
    return {"report_type": "日报", **result}


# ── 全市装维工作量统计横山专用 API ──

@router.get("/reports/city-workload/summary")
async def city_workload_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取全市装维工作量统计横山卡片汇总指标（4个字段）"""
    from app.services.report_scanner import get_city_workload_summary
    return await get_city_workload_summary(db)


@router.get("/reports/city-workload/workers")
async def city_workload_workers(
    db: AsyncSession = Depends(get_db),
):
    """获取全市装维工作量统计横山装维人员工作量明细列表"""
    from app.services.report_scanner import get_city_workload_workers
    return await get_city_workload_workers(db)


@router.post("/reports/city-workload/reparse")
async def city_workload_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析全市装维工作量统计文件，提取横山汇总指标和人员明细"""
    from app.services.report_scanner import reparse_city_workload
    result = await reparse_city_workload(db, directory)
    return {"report_type": "全市装维工作量统计", **result}


# ── 五类工单退撤单情况横山专用 API ──

@router.get("/reports/five-category-withdrawal/summary")
async def five_category_withdrawal_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取五类工单退撤单情况横山卡片指标（日粒度/月粒度退撤总量和重装量）"""
    from app.services.report_scanner import get_five_category_withdrawal_summary
    return await get_five_category_withdrawal_summary(db)


@router.get("/reports/five-category-withdrawal/detail")
async def five_category_withdrawal_detail(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取五类工单退撤单情况横山退撤单明细（15个字段）"""
    from app.services.report_scanner import get_five_category_withdrawal_details
    return await get_five_category_withdrawal_details(db, page, page_size)


@router.post("/reports/five-category-withdrawal/reparse")
async def five_category_withdrawal_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析五类工单退撤单情况文件，提取横山汇总指标和退撤单明细"""
    from app.services.report_scanner import reparse_five_category_withdrawal
    result = await reparse_five_category_withdrawal(db, directory)
    return {"report_type": "五类工单撤撤单情况", **result}


# ── 宽带在途投诉清单横山专用 API ──

@router.get("/reports/complaint-backlog/summary")
async def complaint_backlog_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取宽带在途投诉清单横山卡片指标（10086积压、全球通积压、2200000积压、86线下积压、合计、前一日积压量、环比）"""
    from app.services.report_scanner import get_complaint_backlog_summary
    return await get_complaint_backlog_summary(db)


@router.post("/reports/complaint-backlog/reparse")
async def complaint_backlog_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析宽带在途投诉清单文件，提取横山在途投诉汇总数据"""
    from app.services.report_scanner import reparse_complaint_backlog
    result = await reparse_complaint_backlog(db, directory)
    return {"report_type": "宽带在途投诉清单", **result}
