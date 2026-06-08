from fastapi import APIRouter, Depends, Query, BackgroundTasks
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

from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional, List as _List


class AiChatRequest(_BaseModel):
    message: str
    history: _Optional[_List[dict]] = None


@router.post("/ai/chat")
async def ai_chat(
    req: AiChatRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.ai.service import ai_chat_handler
    return await ai_chat_handler(req.message, db, req.history)


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


# ── 10086投诉积压(督办)横山专用 API ──

@router.get("/reports/complaint-10086/summary")
async def complaint_10086_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取10086投诉积压(督办)横山卡片指标（合计未超时积压、今日需处理量、家宽业务、合计超时积压、合计积压）"""
    from app.services.report_scanner import get_complaint_10086_summary
    return await get_complaint_10086_summary(db)


@router.get("/reports/complaint-10086/detail")
async def complaint_10086_detail(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """分页获取10086投诉积压(督办)横山10086积压清单明细"""
    from app.services.report_scanner import get_complaint_10086_details
    return await get_complaint_10086_details(db, page, page_size)


@router.post("/reports/complaint-10086/reparse")
async def complaint_10086_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析10086投诉积压(督办)文件，提取横山汇总+明细数据"""
    from app.services.report_scanner import reparse_complaint_10086
    result = await reparse_complaint_10086(db, directory)
    return {"report_type": "10086投诉积压(督办)", **result}


# ── 2200000及时率通报 ──

@router.get("/reports/complaint-2200000/summary")
async def complaint_2200000_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取2200000及时率通报横山卡片指标"""
    from app.services.report_scanner import get_complaint_2200000_summary
    return await get_complaint_2200000_summary(db)


@router.get("/reports/complaint-2200000/detail")
async def complaint_2200000_detail(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """分页获取2200000及时率通报横山明细"""
    from app.services.report_scanner import get_complaint_2200000_details
    return await get_complaint_2200000_details(db, page, page_size)


@router.post("/reports/complaint-2200000/reparse")
async def complaint_2200000_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析2200000及时率通报文件，提取横山汇总+明细数据"""
    from app.services.report_scanner import reparse_complaint_2200000
    result = await reparse_complaint_2200000(db, directory)
    return {"report_type": "2200000及时率通报", **result}


# ── 线下派单处理情况 ──

@router.get("/reports/offline-dispatch/summary")
async def offline_dispatch_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取线下派单处理情况横山卡片指标"""
    from app.services.report_scanner import get_offline_dispatch_summary
    return await get_offline_dispatch_summary(db)


@router.post("/reports/offline-dispatch/reparse")
async def offline_dispatch_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析线下派单处理情况文件，提取横山汇总指标"""
    from app.services.report_scanner import reparse_offline_dispatch
    result = await reparse_offline_dispatch(db, directory)
    return {"report_type": "线下派单处理情况", **result}


@router.get("/reports/offline-dispatch/details")
async def offline_dispatch_details(
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """获取线下派单处理情况横山明细数据（支持按分类筛选）"""
    from app.core.models import OfflineDispatchDetail
    from sqlalchemy import select, func

    stmt = select(OfflineDispatchDetail)
    if category:
        stmt = stmt.where(OfflineDispatchDetail.category == category)

    count_stmt = select(func.count(OfflineDispatchDetail.id))
    if category:
        count_stmt = count_stmt.where(OfflineDispatchDetail.category == category)
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = stmt.order_by(OfflineDispatchDetail.id.asc()).offset(offset).limit(page_size)
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    records = []
    for row in rows:
        records.append({
            "id": row.id,
            "district": row.district,
            "timeout_limit": row.timeout_limit,
            "broadband_account": row.broadband_account,
            "is_vip_customer": row.is_vip_customer,
            "customer_contact": row.customer_contact,
            "construction_address": row.construction_address,
            "handler_name": row.handler_name,
            "category": row.category,
        })

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── 重投预警工单梳理 ──

@router.get("/reports/retry-warning/summary")
async def retry_warning_summary(db: AsyncSession = Depends(get_db)):
    """获取重投预警工单梳理横山卡片指标"""
    from app.services.report_scanner import get_retry_warning_summary
    return await get_retry_warning_summary(db)


@router.post("/reports/retry-warning/reparse")
async def retry_warning_reparse(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """重新解析重投预警工单梳理文件"""
    from app.services.report_scanner import reparse_retry_warning
    result = await reparse_retry_warning(db)
    return {"report_type": "重投预警工单梳理", **result}


@router.get("/reports/retry-warning/retry-details")
async def retry_warning_retry_details(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """获取重投预警清单明细（预警1清单）"""
    from app.core.models import RetryWarningDetail
    from sqlalchemy import select, func

    count_stmt = select(func.count(RetryWarningDetail.id))
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = select(RetryWarningDetail).order_by(RetryWarningDetail.id.asc()).offset(offset).limit(page_size)
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    records = []
    for row in rows:
        records.append({
            "id": row.id,
            "district": row.district,
            "retry_count": row.retry_count,
            "broadband_account": row.broadband_account,
            "is_global_user": row.is_global_user,
            "customer_contact": row.customer_contact,
            "construction_address": row.construction_address,
            "days_elapsed": row.days_elapsed,
            "handler_name": row.handler_name,
            "complaint_content": row.complaint_content,
        })

    return {"records": records, "total": total, "page": page, "page_size": page_size}


@router.get("/reports/retry-warning/repair-details")
async def retry_warning_repair_details(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """获取客户催修清单明细（预警2催修未恢复）"""
    from app.core.models import CustomerRepairDetail
    from sqlalchemy import select, func

    count_stmt = select(func.count(CustomerRepairDetail.id))
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = select(CustomerRepairDetail).order_by(CustomerRepairDetail.id.asc()).offset(offset).limit(page_size)
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    records = []
    for row in rows:
        records.append({
            "id": row.id,
            "district": row.district,
            "repair_count": row.repair_count,
            "account": row.account,
            "call_number": row.call_number,
            "address": row.address,
            "register_date": row.register_date,
        })

    return {"records": records, "total": total, "page": page, "page_size": page_size}


# ── 企宽故障率横山专用 API ──

@router.get("/reports/enterprise-broadband-fault/summary")
async def enterprise_broadband_fault_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取企宽故障率横山卡片指标"""
    from app.services.report_scanner import get_enterprise_broadband_fault_summary
    return await get_enterprise_broadband_fault_summary(db)


@router.get("/reports/enterprise-broadband-fault/details")
async def enterprise_broadband_fault_details(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_field: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """分页获取企宽故障率横山故障明细（支持排序和筛选）"""
    from app.services.report_scanner import get_enterprise_broadband_fault_details
    return await get_enterprise_broadband_fault_details(
        db, page, page_size, sort_field, sort_order, district
    )


@router.post("/reports/enterprise-broadband-fault/reparse")
async def enterprise_broadband_fault_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析企宽故障率文件，提取横山汇总指标和故障明细"""
    from app.services.report_scanner import reparse_enterprise_broadband_fault
    result = await reparse_enterprise_broadband_fault(db, directory)
    return {"report_type": "企宽故障率", **result}


# ── 质差小区弱光工单 API ──

@router.get("/reports/poor-quality-work-order/summary")
async def poor_quality_work_order_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取质差小区弱光工单横山卡片指标"""
    from app.services.report_scanner import get_poor_quality_work_order_summary
    return await get_poor_quality_work_order_summary(db)


@router.get("/reports/poor-quality-work-order/details")
async def poor_quality_work_order_details(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取质差小区弱光工单横山未完成明细"""
    from app.services.report_scanner import get_poor_quality_work_order_details
    return await get_poor_quality_work_order_details(db, page, page_size)


@router.post("/reports/poor-quality-work-order/reparse")
async def poor_quality_work_order_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析质差小区弱光工单文件，提取横山汇总指标和未完成工单明细"""
    from app.services.report_scanner import reparse_poor_quality_work_order
    result = await reparse_poor_quality_work_order(db, directory)
    return {"report_type": "质差小区弱光工单处理完成率", **result}


# ── 企宽弱光通报横山专用 API ──

@router.get("/reports/enterprise-broadband-low-light/summary")
async def enterprise_broadband_low_light_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取企宽弱光通报横山卡片指标（企宽总量、月完成量、月完成率、县区排名）"""
    from app.services.report_scanner import get_enterprise_broadband_low_light_summary
    return await get_enterprise_broadband_low_light_summary(db)


@router.get("/reports/enterprise-broadband-low-light/details")
async def enterprise_broadband_low_light_details(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """分页获取企宽弱光通报横山未恢复明细"""
    from app.services.report_scanner import get_enterprise_broadband_low_light_details
    return await get_enterprise_broadband_low_light_details(db, page, page_size)


@router.post("/reports/enterprise-broadband-low-light/reparse")
async def enterprise_broadband_low_light_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析企宽弱光通报文件，提取横山汇总指标和未恢复明细"""
    from app.services.report_scanner import reparse_enterprise_broadband_low_light
    result = await reparse_enterprise_broadband_low_light(db, directory)
    return {"report_type": "企宽弱光通报", **result}


# ── 家宽重投2次清单 API ──

@router.get("/reports/broadband-redelivery2/summary")
async def broadband_redelivery2_summary(
    db: AsyncSession = Depends(get_db),
):
    """获取家宽重投2次横山卡片指标（8项：重投2次在途量、2次全球通量 等）"""
    from app.services.report_scanner import get_broadband_redelivery2_summary
    return await get_broadband_redelivery2_summary(db)


@router.post("/reports/broadband-redelivery2/reparse")
async def broadband_redelivery2_reparse(
    directory: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """重新解析家宽重投2次清单，提取横山最新8项指标"""
    from app.services.report_scanner import reparse_broadband_redelivery2
    result = await reparse_broadband_redelivery2(db, directory)
    return {"report_type": "家宽重投2次清单明细", **result}


# ── 通知 API ──

@router.get("/notifications")
async def list_notifications(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """获取最近的指标更新通知（默认10条）"""
    from app.core.models import Notification
    from sqlalchemy import select as _select

    stmt = (
        _select(Notification)
        .order_by(Notification.event_time.desc())
        .limit(limit)
    )
    r = await db.execute(stmt)
    rows = r.scalars().all()
    return [
        {
            "id": n.id,
            "report_type": n.report_type,
            "filename": n.filename,
            "event_time": n.event_time.isoformat() if n.event_time else None,
            "is_read": n.is_read,
        }
        for n in rows
    ]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """标记通知为已读"""
    from app.core.models import Notification
    from sqlalchemy import update as _update

    stmt = (
        _update(Notification)
        .where(Notification.id == notification_id)
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
):
    """标记所有通知为已读"""
    from app.core.models import Notification
    from sqlalchemy import update as _update

    stmt = _update(Notification).values(is_read=True)
    await db.execute(stmt)
    await db.commit()
    return {"ok": True}
