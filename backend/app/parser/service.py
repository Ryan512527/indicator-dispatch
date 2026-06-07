import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Column header mapping: Chinese → English canonical ──
XLSX_COLUMN_MAP = {
    # 无线退服清单 columns
    "基站类型": "station_type",
    "县区": "district",
    "站号": "station_code",
    "铁塔站址编码": "tower_site_code",
    "站址名称": "site_name",
    "网元名称": "ne_name",
    "告警名称": "alarm_name",
    "告警时间": "alarm_time",
    "退服时长(h)": "outage_duration_hours",
    "停电/FSU离线时间": "power_off_time",
    "是否发电": "has_power_gen",
    "是否安装智能空开": "has_smart_switch",
    "国庆重保": "national_day_guarantee",
    "保障场景": "guarantee_scenario",
    "保障时限(小时)": "guarantee_time_limit",
    "是否超时": "is_timeout",
    "是否塔维": "is_tower_maintenance",
    "机房名称": "room_name",
    "是否短期无法恢复": "short_term_unrecoverable",

    # 榆林皮站故障清单 columns
    "网络类型": "network_type",
    "基站名称": "station_name",
    "网管状态": "nms_status",
    "设备厂商": "vendor",
    "设备类型": "device_type",
    "最后离线时间": "last_offline_time",

    # 接入层通报 columns
    "县区": "district",
    "告警码名称": "alarm_code_name",
    "发生时间": "occurrence_time",
    "具体原因": "specific_reason",
    "责任人": "responsible_person",
    "是否影响业务": "business_affected",
    "故障历时": "fault_duration",
    "接入层断纤链路清单": "fiber_break_link",

    # 考核指标算法 columns
    "序号": "seq",
    "描述对象": "object_desc",
    "描述对象2": "object_desc2",
    "指标名": "indicator_name",
    "指标英文名": "indicator_code",
    "统计算法": "calc_algorithm",
    "指标等级": "indicator_level",
    "最低采集周期": "min_collect_cycle",
    "采集单位": "unit",
    "告警规则": "alarm_rule",
    "应用场景": "application_scenario",
}

# ── Mapping from column type to indicator dimension ──
DIMENSION_COLUMNS = {
    "district", "station_type", "network_type", "alarm_name", "nms_status",
    "vendor", "device_type", "has_power_gen", "has_smart_switch",
    "is_timeout", "is_tower_maintenance", "short_term_unrecoverable",
    "national_day_guarantee", "guarantee_scenario",
}

# Numeric value columns
VALUE_COLUMNS = {
    "outage_duration_hours", "guarantee_time_limit",
}

# Time columns
TIME_COLUMNS = {
    "alarm_time", "power_off_time", "last_offline_time",
}


def parse_file(filepath: str) -> list[dict]:
    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".csv":
            return _parse_csv(filepath)
        elif ext == ".json":
            return _parse_json(filepath)
        elif ext in (".xlsx", ".xls"):
            return _parse_excel(filepath)
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []
    except Exception as e:
        logger.error(f"Parse failed for {filepath}: {e}", exc_info=True)
        return []


# ── CSV ──
def _parse_csv(filepath: str) -> list[dict]:
    import pandas as pd
    df = pd.read_csv(filepath)
    return _df_to_records(df, filepath)


# ── Excel ──
def _parse_excel(filepath: str) -> list[dict]:
    import pandas as pd

    xls = pd.ExcelFile(filepath, engine="openpyxl")

    # Try each sheet
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        records = _parse_excel_sheet(df, filepath, sheet_name)
        if records:
            return records

    # Fallback: read all sheets
    all_records = []
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        records = _parse_excel_sheet(df, filepath, sheet_name)
        all_records.extend(records)
    return all_records


def _parse_excel_sheet(df, filepath: str, sheet_name: str) -> list[dict]:
    df = df.dropna(how="all").fillna("")

    if df.empty:
        return []

    # Detect header: find first row that has known Chinese column headers
    header_row_idx = None
    column_mapping = {}

    for idx, row in df.iterrows():
        row_text = " ".join(str(v) for v in row.values if v)
        matched_cols = {}
        for cn_name, en_name in XLSX_COLUMN_MAP.items():
            for cell in row.values:
                if str(cell).strip() == cn_name:
                    matched_cols[cn_name] = en_name
                    break

        if len(matched_cols) >= 3:  # Found header row
            header_row_idx = idx
            column_mapping = matched_cols
            break

    if header_row_idx is None:
        return []

    # Parse title from cell A1 if it's a merged title
    title_text = ""
    first_cell = str(df.iloc[0, 0]) if df.shape[1] > 0 else ""
    if first_cell and not any(
        str(first_cell).strip() == cn for cn in XLSX_COLUMN_MAP
    ):
        title_text = str(first_cell).strip()

    # Extract timestamp & location from title
    parsed_time, parsed_location = _parse_title(title_text)
    if parsed_time is None:
        # Fall back to file modification time
        parsed_time = datetime.fromtimestamp(
            os.path.getmtime(filepath), tz=timezone.utc
        )

    # Build English header mapping (support keyword containment for date-suffixed columns)
    en_headers = []
    for cell in df.iloc[header_row_idx].values:
        cell_str = str(cell).strip()
        # Try exact match first, then keyword containment via full XLSX_COLUMN_MAP
        mapped = XLSX_COLUMN_MAP.get(cell_str)
        if mapped is None:
            for cn_name, en_name in XLSX_COLUMN_MAP.items():
                if len(cn_name) > 2 and cn_name in cell_str:
                    mapped = en_name
                    break
        en_headers.append(mapped or cell_str)

    # Parse data rows
    records = []
    for data_idx in range(header_row_idx + 1, len(df)):
        row = df.iloc[data_idx]
        record = {}
        has_data = False
        for ci, val in enumerate(row.values):
            if ci < len(en_headers):
                key = en_headers[ci]
                v = str(val).strip() if val != "" and str(val).strip() != "" else ""
                if v:
                    has_data = True
                record[key] = v

        if not has_data:
            continue

        # Convert Excel serial dates to ISO datetime strings
        for tcol in ("occurrence_time", "alarm_time"):
            if tcol in record and record[tcol]:
                try:
                    serial = float(record[tcol])
                    if serial > 40000:  # Looks like an Excel serial date
                        dt_val = _excel_serial_to_dt(serial)
                        if dt_val:
                            record[tcol] = dt_val.isoformat()
                except (ValueError, TypeError):
                    pass

        # Fault duration - store raw formula value (in hours, from =(NOW()-E2)*24)
        if "fault_duration" in record and record["fault_duration"]:
            try:
                record["fault_duration"] = round(float(record["fault_duration"]), 2)
            except (ValueError, TypeError):
                pass

        # Set defaults from title
        record["_source_file"] = os.path.basename(filepath)
        record["_parsed_time"] = parsed_time.isoformat()
        if parsed_location:
            record["_parsed_location"] = parsed_location

        records.append(record)

    return records


import datetime as _dt_mod

def _excel_serial_to_dt(serial: float) -> datetime | None:
    """Convert Excel serial date number to datetime"""
    try:
        return _dt_mod.datetime(1899, 12, 30, tzinfo=timezone.utc) + _dt_mod.timedelta(days=float(serial))
    except (ValueError, TypeError, OverflowError):
        return None

def _parse_title(title: str) -> tuple:
    """Parse title like '2026-06-03 09:02榆林无线退服清单'"""
    # Extract timestamp from beginning
    ts_match = re.match(
        r"(\d{4})[年\-](\d{1,2})[月\-](\d{1,2})[日 ]?(\d{1,2})[点时](\d{1,2})分?",
        title,
    )
    if ts_match:
        parts = [int(x) for x in ts_match.groups()]
        parsed = datetime(parts[0], parts[1], parts[2], parts[3], parts[4], tzinfo=timezone.utc)
        remaining = title[ts_match.end():]
        # Extract location (e.g. 榆林)
        loc_match = re.match(r"([\u4e00-\u9fa5]{2,4})", remaining)
        location = loc_match.group(1) if loc_match else None
        return parsed, location

    # Try ISO format
    try:
        parsed = datetime.fromisoformat(title[:19])
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        remaining = title[19:]
        loc_match = re.match(r"([\u4e00-\u9fa5]{2,4})", remaining)
        return parsed, loc_match.group(1) if loc_match else None
    except (ValueError, IndexError):
        return None, None


# ── JSON ──
def _parse_json(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("records", data.get("data", [data]))
    else:
        records = [data]

    parsed_time = datetime.fromtimestamp(
        os.path.getmtime(filepath), tz=timezone.utc
    )
    fname = os.path.basename(filepath)
    for r in records:
        r["_source_file"] = fname
        r.setdefault("_parsed_time", parsed_time.isoformat())
    return records


def _df_to_records(df, filepath: str) -> list[dict]:
    import pandas as pd
    df = df.dropna(how="all")
    records = df.to_dict(orient="records")
    fname = os.path.basename(filepath)
    now = datetime.now(timezone.utc).isoformat()
    for r in records:
        r["_source_file"] = fname
        r.setdefault("_parsed_time", now)
    return records
