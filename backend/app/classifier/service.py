import logging
import uuid
import re
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from app.core.database import async_session
from app.core.models import IndicatorDefinition, IndicatorEvent

logger = logging.getLogger(__name__)

# ── Field categorization ──
TIME_COLUMNS = {"alarm_time", "power_off_time", "last_offline_time", "time", "timestamp", "date"}
VALUE_COLUMNS = {"outage_duration_hours", "fault_duration", "val", "count", "amount"}
NAME_COLUMNS = {"indicator_name", "name", "indicator"}
CODE_COLUMNS = {"indicator_code", "code", "indicator_english_name"}
CATEGORY_COLUMNS = {"category", "object_desc"}

# ── District filter ──
DISTRICT_FILTER = "横山"

# ── Dimensions to store (extensible: add new keys here later) ──
STORED_DIMENSIONS = {
    "station_type",          # 基站类型
    "site_name",             # 站址名称
    "alarm_name",            # 告警名称
    "alarm_time",            # 告警时间
    "guarantee_scenario",    # 保障场景
    "is_timeout",            # 是否超时
    "is_tower_maintenance",  # 是否塔维
    "guarantee_time_limit",  # 保障时限(小时)
    "fiber_break_link",      # 接入层断纤链路清单
    "occurrence_time",       # 发生时间
    "specific_reason",       # 具体原因
    "business_affected",     # 是否影响业务
    "fault_duration",        # 故障历时
    "alarm_code_name",       # 告警码名称
    "responsible_person",    # 责任人
}

SOURCE_COLUMNS = {"source", "_source_file"}


async def classify_and_store(records: list[dict]) -> int:
    # Filter by district first
    filtered = [r for r in records if DISTRICT_FILTER in r.get("district", "")]
    logger.info(f"District filter '{DISTRICT_FILTER}': {len(filtered)} / {len(records)} records")

    stored = 0
    async with async_session() as session:
        for record in filtered:
            try:
                indicator = await _resolve_indicator(session, record)
                event = _build_event(record, indicator.id)
                session.add(event)
                stored += 1
            except Exception as e:
                logger.warning(f"Skipping record: {e}")

        await session.commit()

    logger.info(f"Stored {stored} records")
    return stored


async def _resolve_indicator(session, record: dict) -> IndicatorDefinition:
    indicator_name = _extract_field(record, NAME_COLUMNS)
    indicator_code = _extract_field(record, CODE_COLUMNS)
    source_file = record.get("_source_file", "")
    alarm_name = record.get("alarm_name", "")
    specific_reason = record.get("specific_reason", "")

    if not indicator_name:
        if "无线退服清单" in source_file:
            indicator_name = f"无线退服 - {alarm_name}" if alarm_name else "无线退服数量"
        elif "皮站故障清单" in source_file:
            indicator_name = f"皮站故障 - {alarm_name}" if alarm_name else "皮站故障数量"
        elif "接入层通报" in source_file:
            indicator_name = f"接入层故障 - {specific_reason}" if specific_reason else "接入层故障"
        else:
            indicator_name = f"指标_{uuid.uuid4().hex[:8]}"

    if not indicator_code:
        indicator_code = f"auto_{re.sub(r'[^a-zA-Z0-9]', '_', indicator_name)[:40]}"

    result = await session.execute(
        select(IndicatorDefinition).where(IndicatorDefinition.code == indicator_code)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    category = _extract_field(record, CATEGORY_COLUMNS)
    if not category:
        if "无线退服" in source_file:
            category = "无线退服"
        elif "皮站故障" in source_file:
            category = "皮站故障"
        elif "家宽故障率" in source_file:
            category = "家宽故障"
        elif "接入层通报" in source_file:
            category = "接入层故障"
        elif "退撤单" in source_file:
            category = "工单退撤"

    indicator = IndicatorDefinition(
        id=uuid.uuid4(),
        name=indicator_name,
        code=indicator_code,
        category=category,
    )
    session.add(indicator)
    await session.flush()
    return indicator


def _build_event(record: dict, indicator_id: uuid.UUID) -> IndicatorEvent:
    parsed_time_str = record.get("_parsed_time")
    alarm_time_str = _extract_field(record, TIME_COLUMNS)
    event_time = _parse_time(parsed_time_str or alarm_time_str)

    # Use the raw 退服时长(h) value from the source file
    value = _extract_numeric(record, VALUE_COLUMNS) or 1.0

    source = record.get("_source_file", "")

    # Only store the dimensions defined in STORED_DIMENSIONS
    dimensions = {}
    for key in STORED_DIMENSIONS:
        val = record.get(key)
        if val is not None and str(val).strip():
            dimensions[key] = str(val).strip()

    event = IndicatorEvent(
        id=uuid.uuid4(),
        time=event_time,
        indicator_id=indicator_id,
        value=value,
        source=source,
        dimensions=dimensions,
        extra_data={"raw": dict(dimensions)},
    )
    return event


def _extract_field(record: dict, candidates: set) -> Any:
    for key in candidates:
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    rec_lower = {k.lower(): str(v) for k, v in record.items()}
    for key in candidates:
        v = rec_lower.get(key.lower())
        if v and v.strip():
            return v.strip()
    return None


def _extract_numeric(record: dict, candidates: set) -> float | None:
    for key in candidates:
        val = record.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None


def _parse_time(s: str | None) -> datetime:
    now = datetime.now(timezone.utc)
    if not s:
        return now
    s = str(s).strip()
    patterns = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y年%m月%d日 %H点%M分",
        "%Y年%m月%d日%H点%M分",
    ]
    for fmt in patterns:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return now
