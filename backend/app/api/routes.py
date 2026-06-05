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
