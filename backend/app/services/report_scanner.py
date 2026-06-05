"""
报表扫描与通用解析服务
- 按关键词识别报表类型
- 出现 ≥3 次的报表类型视为"目标报表"
- 通用解析：读取 Excel 全部行列，存入 report_records 表
"""
import os
import re
import glob
import logging
import asyncio
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional, List, Dict

import openpyxl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.core.models import ReportType, ReportFile, ReportRecord
from app.core.config import settings

logger = logging.getLogger(__name__)

# 报表类型关键词（按优先级匹配，长的优先）
REPORT_KEYWORDS: List[str] = [
    "家宽+FTTR遗留工单安装进度通报",
    "质差小区弱光工单处理完成率",
    "宽带在途投诉清单",
    "成功率攻坚通报",
    "质差客户整治完成率通报",
    "全市装维工作量统计",
    "投诉积压大于3单人员通报",
    "投诉积压通报新",
    "企宽开通及时率通报",
    "企宽故障率",
    "企宽装机通报",
    "线下派单处理情况",
    "重投预警工单梳理",
    "家宽重投2次清单明细",
    "投诉三类工单在途情况",
    "H5当日闭环测评清单",
    "2200000及时率通报",
    "一二级分支真实处理通报",
    "长历时通报",
    "触点用后即评",
    "五类工单退撤单情况",
    "装机履约及时率",
    "一户一案",
    "企宽弱光通报",
    "企宽分支在途工单",
    "榆林未恢复故障统计",
    "接入层通报",
    "皮站故障清单",
    "无线退服清单",
    "日报",
]


def identify_report_type(filename: str) -> Optional[str]:
    """根据文件名识别报表类型，匹配最长关键词"""
    for keyword in REPORT_KEYWORDS:
        if keyword in filename:
            return keyword
    return None


def scan_target_reports(directory: str, min_occurrences: int = 3) -> List[Dict]:
    """
    递归扫描目录，按报表类型分组，返回出现次数 ≥ min_occurrences 的报表类型列表。
    每条记录：{"report_type": str, "file_count": int, "files": [filename, ...]}
    """
    patterns = (".xlsx", ".xls", ".csv")
    all_files: List[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if f.lower().endswith(patterns):
                all_files.append(os.path.join(root, f))

    groups: Dict[str, List[str]] = defaultdict(list)
    for filepath in all_files:
        filename = os.path.basename(filepath)
        report_type = identify_report_type(filename)
        if report_type:
            groups[report_type].append(filepath)

    result: List[Dict] = []
    for report_type, files in groups.items():
        if len(files) >= min_occurrences:
            result.append({
                "report_type": report_type,
                "file_count": len(files),
                "files": [os.path.basename(f) for f in files],
            })

    return sorted(result, key=lambda x: -x["file_count"])


async def scan_and_register(directory: str, db: AsyncSession) -> List[Dict]:
    """
    扫描目录，识别目标报表类型，注册到 report_types 表。
    返回 [{"name": ..., "status": "registered"/"exists", "file_count": ...}, ...]
    """
    target_reports = scan_target_reports(directory)
    result = []

    for tr in target_reports:
        name = tr["report_type"]
        stmt = select(ReportType).where(ReportType.name == name)
        r = await db.execute(stmt)
        existing = r.scalar_one_or_none()

        if not existing:
            rt = ReportType(name=name, category="")
            db.add(rt)
            await db.flush()
            result.append({"name": name, "status": "registered", "file_count": tr["file_count"]})
        else:
            result.append({"name": name, "status": "exists", "file_count": tr["file_count"]})

    await db.commit()
    return result


def _parse_excel_sync(file_path: str) -> List[Dict]:
    """
    同步解析 Excel 文件，返回 [row_dict, ...]。
    在线程池中调用，避免阻塞事件循环。
    """
    ext = os.path.splitext(file_path)[1].lower()
    rows_data: List[tuple] = []

    if ext == ".xlsx":
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        rows_data = list(ws.iter_rows(values_only=True))
        wb.close()
    else:
        # 尝试用 openpyxl 读取 .xls（部分兼容）
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            rows_data = list(ws.iter_rows(values_only=True))
            wb.close()
        except Exception:
            raise ValueError(f"不支持的文件格式: {ext}，仅支持 .xlsx")

    if not rows_data or len(rows_data) < 2:
        return []

    # 第一行作为表头
    raw_headers = rows_data[0]
    headers: List[str] = []
    for i, h in enumerate(raw_headers):
        if h is not None:
            headers.append(str(h).strip())
        else:
            # 查找最近的非空表头
            headers.append(f"col_{i}")

    data: List[Dict] = []
    for row in rows_data[1:]:
        row_dict: Dict[str, str] = {}
        for i, cell in enumerate(row):
            header = headers[i] if i < len(headers) else f"col_{i}"
            if cell is None:
                row_dict[header] = ""
            elif isinstance(cell, datetime):
                row_dict[header] = cell.isoformat()
            else:
                row_dict[header] = str(cell)
        data.append(row_dict)

    return data


async def parse_report_type(
    report_type_name: str,
    db: AsyncSession,
    directory: Optional[str] = None,
    update_column_hint: bool = True,
) -> Dict:
    """
    解析指定报表类型的所有文件，入库。
    返回 {"total_records": int, "files_parsed": int, "files_skipped": int}
    """
    if directory is None:
        directory = settings.watch_dir

    # 收集匹配文件（递归）
    all_files: List[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if f.lower().endswith((".xlsx", ".xls", ".csv")):
                all_files.append(os.path.join(root, f))
    matching_files = [f for f in all_files if report_type_name in os.path.basename(f)]

    # 获取或创建 ReportType
    stmt = select(ReportType).where(ReportType.name == report_type_name)
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name=report_type_name, category="")
        db.add(report_type)
        await db.flush()

    total_records = 0
    files_parsed = 0
    files_skipped = 0
    all_columns: set = set()

    for filepath in matching_files:
        filename = os.path.basename(filepath)
        # 检查是否已解析
        stmt2 = select(ReportFile).where(ReportFile.filename == filename)
        r2 = await db.execute(stmt2)
        existing = r2.scalar_one_or_none()

        if existing and existing.parse_status == "parsed":
            logger.info(f"跳过已解析文件: {filename}")
            files_skipped += 1
            continue

        try:
            rows = await asyncio.to_thread(_parse_excel_sync, filepath)
            if not rows:
                files_skipped += 1
                continue

            # 创建/更新 ReportFile
            if existing:
                report_file = existing
            else:
                report_file = ReportFile(
                    report_type_id=report_type.id,
                    filename=filename,
                    file_path=filepath,
                )
                db.add(report_file)
            await db.flush()

            # 幂等：删除旧记录
            await db.execute(delete(ReportRecord).where(ReportRecord.report_file_id == report_file.id))

            # 写入新记录
            for row in rows:
                db.add(ReportRecord(report_file_id=report_file.id, data=row))
                all_columns.update(row.keys())

            report_file.record_count = len(rows)
            report_file.parse_status = "parsed"
            report_file.parse_error = None
            total_records += len(rows)
            files_parsed += 1
            logger.info(f"已解析 {filename}: {len(rows)} 条记录")

        except Exception as e:
            logger.error(f"解析失败 {filename}: {e}")
            if existing is None:
                report_file = ReportFile(
                    report_type_id=report_type.id,
                    filename=filename,
                    file_path=filepath,
                    parse_status="failed",
                    parse_error=str(e),
                )
                db.add(report_file)
            else:
                existing.parse_status = "failed"
                existing.parse_error = str(e)
            files_skipped += 1

    # 更新 column_hint
    if update_column_hint and all_columns:
        report_type.column_hint = list(all_columns)
        report_type.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {
        "total_records": total_records,
        "files_parsed": files_parsed,
        "files_skipped": files_skipped,
    }


async def get_report_types(db: AsyncSession) -> List[Dict]:
    """获取所有报表类型及统计信息"""
    stmt = select(ReportType).order_by(ReportType.id)
    r = await db.execute(stmt)
    types = r.scalars().all()

    result = []
    for rt in types:
        # 统计文件数和记录数
        f_stmt = select(func.count(ReportFile.id)).where(
            ReportFile.report_type_id == rt.id,
            ReportFile.parse_status == "parsed",
        )
        r2 = await db.execute(f_stmt)
        file_count = r2.scalar() or 0

        r_stmt = (
            select(func.count(ReportRecord.id))
            .join(ReportFile)
            .where(ReportFile.report_type_id == rt.id)
        )
        r3 = await db.execute(r_stmt)
        record_count = r3.scalar() or 0

        # 最新文件时间 & 预览数据
        t_stmt = select(ReportFile).where(
            ReportFile.report_type_id == rt.id,
            ReportFile.parse_status == "parsed",
        ).order_by(ReportFile.created_at.desc()).limit(1)
        r4 = await db.execute(t_stmt)
        latest_file = r4.scalar_one_or_none()
        latest_time = latest_file.created_at if latest_file else None
        latest_filename = latest_file.filename if latest_file else None

        # 最新文件的前5条记录作为预览
        latest_preview: List[Dict] = []
        if latest_file:
            p_stmt = select(ReportRecord.data).where(
                ReportRecord.report_file_id == latest_file.id
            ).limit(5)
            r5 = await db.execute(p_stmt)
            latest_preview = [dict(row[0]) for row in r5.all()]

        result.append({
            "id": rt.id,
            "name": rt.name,
            "category": rt.category,
            "column_hint": rt.column_hint or [],
            "file_count": file_count,
            "record_count": record_count,
            "latest_time": latest_time.isoformat() if latest_time else None,
            "latest_filename": latest_filename,
            "latest_preview": latest_preview,
            "created_at": rt.created_at.isoformat() if rt.created_at else None,
        })

    return result


# ── 无线退服横山数据专用处理 ──

# 无线退服清单保留字段（仅提取这9个字段）
WIRELESS_OUTAGE_FIELDS = [
    "基站类型",      # station_type
    "站址名称",      # site_name
    "告警名称",      # alarm_name
    "告警时间",      # alarm_time
    "退服时长(h)",   # outage_duration_hours
    "保障场景",      # guarantee_scenario
    "是否超时",      # is_timeout
    "是否塔维",      # is_tower_maintenance
    "机房名称",      # room_name
]

# 英文到中文映射（用于 API 返回，保留中文原名）
WIRELESS_OUTAGE_FIELD_MAP = {
    "基站类型": "基站类型",
    "站址名称": "站址名称",
    "告警名称": "告警名称",
    "告警时间": "告警时间",
    "退服时长(h)": "退服时长(h)",
    "保障场景": "保障场景",
    "是否超时": "是否超时",
    "是否塔维": "是否塔维",
    "机房名称": "机房名称",
}


# 无线退服: parser 英文字段 → 展示中文名称的映射
WIRELESS_OUTAGE_EN_TO_CN = {
    "station_type": "基站类型",
    "site_name": "站址名称",
    "alarm_name": "告警名称",
    "alarm_time": "告警时间",
    "outage_duration_hours": "退服时长(h)",
    "guarantee_scenario": "保障场景",
    "is_timeout": "是否超时",
    "is_tower_maintenance": "是否塔维",
    "room_name": "机房名称",
}


def _parse_wireless_outage_files(directory: str) -> List[Dict]:
    """
    解析所有"无线退服清单"文件，使用 parser 模块正确检测表头，
    仅保留 县区=="横山" 且 9 个指定字段的记录。
    返回 [{"filename": str, "records": [dict]}, ...]
    """
    from app.parser.service import parse_file as parser_parse_file
    all_results: List[Dict] = []

    # 递归查找匹配文件
    matching: List[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "无线退服清单" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    # 按文件修改时间排序（旧的先处理，新的后处理 → 新文件 id 更大）
    matching.sort(key=lambda f: os.path.getmtime(f))

    for filepath in matching:
        filename = os.path.basename(filepath)
        try:
            # 使用 parser 模块正确解析（会检测表头行并做中英映射）
            rows = parser_parse_file(filepath)
            if not rows:
                continue

            filtered: List[Dict] = []
            for row in rows:
                # parser 返回的是英文字段名，district 对应 "县区"
                district = row.get("district", "")
                if district != "横山":
                    continue

                # 只提取 9 个指定字段，映射为中文名称
                clean: Dict[str, str] = {}
                for en_key, cn_key in WIRELESS_OUTAGE_EN_TO_CN.items():
                    val = row.get(en_key, "")
                    clean[cn_key] = str(val) if val is not None else ""
                filtered.append(clean)

            all_results.append({
                "filename": filename,
                "records": filtered,
            })
            if filtered:
                logger.info(f"无线退服横山: {filename} -> {len(filtered)} 条横山记录")
            else:
                logger.info(f"无线退服横山: {filename} -> 0 条横山记录（最新）")

        except Exception as e:
            logger.error(f"解析无线退服文件失败 {filename}: {e}")

    return all_results


async def reparse_wireless_outage(db: AsyncSession, directory: Optional[str] = None) -> Dict:
    """
    重新解析无线退服清单文件，仅保留横山区 9 个字段，更新数据库。
    删除旧的无线退服 report_records 并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 获取或创建"无线退服清单"报表类型
    stmt = select(ReportType).where(ReportType.name == "无线退服清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="无线退服清单", category="无线")
        db.add(report_type)
        await db.flush()

    # 删除旧的无线退服记录（通过 report_files 关联删除 report_records）
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        from sqlalchemy import delete as _delete
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 在线程池中解析
    file_results = await asyncio.to_thread(_parse_wireless_outage_files, directory)

    total_records = 0
    files_parsed = 0
    files_skipped = 0
    all_columns = set(WIRELESS_OUTAGE_FIELDS)

    for fr in file_results:
        filename = fr["filename"]
        records = fr["records"]

        report_file = ReportFile(
            report_type_id=report_type.id,
            filename=filename,
            file_path=os.path.join(directory, filename),
            parse_status="parsed",
            record_count=len(records),
        )
        db.add(report_file)
        await db.flush()

        for row in records:
            db.add(ReportRecord(report_file_id=report_file.id, data=row))

        total_records += len(records)
        if records:
            files_parsed += 1
        else:
            files_skipped += 1

    # 更新 column_hint
    report_type.column_hint = list(all_columns)
    report_type.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "total_records": total_records,
        "files_parsed": files_parsed,
        "files_skipped": files_skipped,
    }


async def get_wireless_outage_summary(db: AsyncSession) -> Dict:
    """获取无线退服横山数据概要：仅最新一份文件的退服数 + 告警名称列表"""
    stmt = select(ReportType).where(ReportType.name == "无线退服清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return {"total": 0, "alarm_names": [], "latest_time": None, "latest_filename": None}

    # 找到最新的 ReportFile（按 id 降序，id 大的 = 最新入库）
    latest_file_stmt = (
        select(ReportFile.id, ReportFile.filename, ReportFile.record_count)
        .where(ReportFile.report_type_id == report_type.id)
        .order_by(ReportFile.id.desc())
        .limit(1)
    )
    r2 = await db.execute(latest_file_stmt)
    latest_row = r2.first()
    if not latest_row:
        return {"total": 0, "alarm_names": [], "latest_time": None, "latest_filename": None}

    latest_file_id, latest_filename, record_count = latest_row

    # 如果最新文件记录数为 0，直接返回
    if record_count == 0:
        return {"total": 0, "alarm_names": [], "latest_time": None, "latest_filename": latest_filename}

    # 仅查询最新文件的记录
    data_stmt = (
        select(ReportRecord.data)
        .where(ReportRecord.report_file_id == latest_file_id)
        .order_by(ReportRecord.id.desc())
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    records = [dict(row[0]) for row in rows]

    alarm_names: List[str] = []
    seen_names = set()
    for rec in records:
        name = rec.get("告警名称", "")
        if name and name not in seen_names:
            alarm_names.append(name)
            seen_names.add(name)

    latest_time = records[0].get("告警时间", "") if records else None

    return {
        "total": len(records),
        "alarm_names": alarm_names,
        "latest_time": latest_time,
        "latest_filename": latest_filename,
    }


async def get_wireless_outage_detail(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> Dict:
    """分页获取无线退服横山详细数据：仅最新一份文件的数据（9个字段）"""
    stmt = select(ReportType).where(ReportType.name == "无线退服清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": None}

    # 找到最新的 ReportFile
    latest_file_stmt = (
        select(ReportFile.id, ReportFile.filename, ReportFile.record_count)
        .where(ReportFile.report_type_id == report_type.id)
        .order_by(ReportFile.id.desc())
        .limit(1)
    )
    r2 = await db.execute(latest_file_stmt)
    latest_row = r2.first()
    if not latest_row:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": None}

    latest_file_id, latest_filename, record_count = latest_row

    if record_count == 0:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": latest_filename}

    # 仅查询最新文件的记录
    data_stmt = (
        select(ReportRecord.data, ReportFile.filename, ReportRecord.created_at)
        .join(ReportFile, ReportRecord.report_file_id == ReportFile.id)
        .where(ReportRecord.report_file_id == latest_file_id)
        .order_by(ReportRecord.id.desc())
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    all_records = []
    for row in rows:
        data, filename, created_at = row
        record = dict(data)
        record["_source_file"] = filename
        record["_created_at"] = created_at.isoformat() if created_at else ""
        all_records.append(record)

    total = len(all_records)

    # 分页
    offset = (page - 1) * page_size
    records = all_records[offset:offset + page_size]

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "latest_filename": latest_filename,
    }


async def get_wireless_outage_trend(db: AsyncSession, hours: int = 48) -> List[Dict]:
    """
    获取最近 N 小时无线退服横山数量趋势（按告警发生时间聚合）。
    去重：同一 (站址名称, 告警名称, 告警时间) 只计一次。
    返回 [{"hour": "2026-06-05T10:00", "count": 3}, ...]
    """
    from collections import Counter
    from datetime import timedelta, timezone as _tz

    stmt = select(ReportType).where(ReportType.name == "无线退服清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return []

    j = ReportRecord.__table__.join(ReportFile.__table__,
        ReportRecord.report_file_id == ReportFile.id)

    data_stmt = (
        select(ReportRecord.data)
        .select_from(j)
        .where(ReportFile.report_type_id == report_type.id)
    )
    r2 = await db.execute(data_stmt)
    rows = r2.all()

    # 北京时间 UTC+8
    beijing_tz = _tz(timedelta(hours=8))
    now_bj = datetime.now(beijing_tz)
    cutoff = now_bj.replace(minute=0, second=0, microsecond=0)

    hour_counter: Counter = Counter()
    seen_alarms: set = set()

    for row in rows:
        data = dict(row[0])
        alarm_time_str = data.get("告警时间", "")
        site_name = data.get("站址名称", "")
        alarm_name = data.get("告警名称", "")

        if not alarm_time_str:
            continue

        # 去重：同一站点+同一告警+同一时间只计一次
        dedup_key = (site_name, alarm_name, alarm_time_str)
        if dedup_key in seen_alarms:
            continue
        seen_alarms.add(dedup_key)

        try:
            # 解析北京时间字符串
            alarm_dt = None
            for fmt_str in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
            ]:
                try:
                    alarm_dt = datetime.strptime(alarm_time_str[:19], fmt_str[:len(alarm_time_str[:19])])
                    break
                except ValueError:
                    continue

            if alarm_dt is None:
                continue

            # 添加北京时区使其与 cutoff 对齐
            alarm_dt = alarm_dt.replace(tzinfo=beijing_tz)

            # 按小时聚合（北京时间）
            hour_key = alarm_dt.replace(minute=0, second=0, microsecond=0)
            hour_counter[hour_key] += 1

        except Exception:
            continue

    # 生成最近 hours 小时的时间序列（北京时间）
    trend = []
    for i in range(hours - 1, -1, -1):
        actual_slot = cutoff - timedelta(hours=i)
        count = hour_counter.get(actual_slot, 0)
        trend.append({
            "hour": actual_slot.isoformat(),
            "count": count,
        })

    return trend


# ── 皮站故障横山数据专用处理 ──

# 皮站故障清单保留字段（仅提取这5个字段）
PISITE_FAULT_FIELDS = [
    "网络类型",      # network_type
    "基站名称",      # station_name
    "网管状态",      # nms_status
    "设备厂商",      # vendor
    "设备类型",      # device_type
]

# 英文到中文映射
PISITE_FAULT_EN_TO_CN = {
    "network_type": "网络类型",
    "station_name": "基站名称",
    "nms_status": "网管状态",
    "vendor": "设备厂商",
    "device_type": "设备类型",
}


def _parse_pisite_fault_files(directory: str) -> list[dict]:
    """
    解析所有"皮站故障清单"文件，使用 parser 模块正确检测表头，
    仅保留 县区=="横山" 且 5 个指定字段的记录。
    返回 [{"filename": str, "records": [dict]}, ...]
    """
    from app.parser.service import parse_file as parser_parse_file
    all_results: list[dict] = []

    # 递归查找匹配文件
    matching: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "皮站故障清单" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    # 按文件修改时间排序（旧的先处理，新的后处理 → 新文件 id 更大）
    matching.sort(key=lambda f: os.path.getmtime(f))

    for filepath in matching:
        filename = os.path.basename(filepath)
        try:
            # 使用 parser 模块正确解析（会检测表头行并做中英映射）
            rows = parser_parse_file(filepath)
            if not rows:
                continue

            filtered: list[dict] = []
            for row in rows:
                # parser 返回的是英文字段名，district 对应 "县区"
                district = row.get("district", "")
                if district != "横山":
                    continue

                # 只提取 5 个指定字段，映射为中文名称
                clean: dict[str, str] = {}
                for en_key, cn_key in PISITE_FAULT_EN_TO_CN.items():
                    val = row.get(en_key, "")
                    clean[cn_key] = str(val) if val is not None else ""
                filtered.append(clean)

            all_results.append({
                "filename": filename,
                "records": filtered,
            })
            if filtered:
                logger.info(f"皮站故障横山: {filename} -> {len(filtered)} 条横山记录")
            else:
                logger.info(f"皮站故障横山: {filename} -> 0 条横山记录")

        except Exception as e:
            logger.error(f"解析皮站故障文件失败 {filename}: {e}")

    return all_results


async def reparse_pisite_fault(db: AsyncSession, directory: Optional[str] = None) -> dict:
    """
    重新解析皮站故障清单文件，仅保留横山区 5 个字段，更新数据库。
    删除旧的皮站故障 report_records 并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 获取或创建"皮站故障清单"报表类型
    stmt = select(ReportType).where(ReportType.name == "皮站故障清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="皮站故障清单", category="故障")
        db.add(report_type)
        await db.flush()

    # 删除旧的皮站故障记录（通过 report_files 关联删除 report_records）
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        from sqlalchemy import delete as _delete
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 在线程池中解析
    file_results = await asyncio.to_thread(_parse_pisite_fault_files, directory)

    total_records = 0
    files_parsed = 0
    files_skipped = 0
    all_columns = set(PISITE_FAULT_FIELDS)

    for fr in file_results:
        filename = fr["filename"]
        records = fr["records"]

        report_file = ReportFile(
            report_type_id=report_type.id,
            filename=filename,
            file_path=os.path.join(directory, filename),
            parse_status="parsed",
            record_count=len(records),
        )
        db.add(report_file)
        await db.flush()

        for row in records:
            db.add(ReportRecord(report_file_id=report_file.id, data=row))

        total_records += len(records)
        if records:
            files_parsed += 1
        else:
            files_skipped += 1

    # 更新 column_hint
    report_type.column_hint = list(all_columns)
    report_type.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "total_records": total_records,
        "files_parsed": files_parsed,
        "files_skipped": files_skipped,
    }


async def get_pisite_fault_summary(db: AsyncSession) -> dict:
    """获取皮站故障横山数据概要：仅最新一份文件的故障总数 + 设备厂商列表"""
    stmt = select(ReportType).where(ReportType.name == "皮站故障清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return {"total": 0, "vendors": [], "latest_time": None, "latest_filename": None}

    # 找到最新的 ReportFile（按 id 降序，id 大的 = 最新入库）
    latest_file_stmt = (
        select(ReportFile.id, ReportFile.filename, ReportFile.record_count)
        .where(ReportFile.report_type_id == report_type.id)
        .order_by(ReportFile.id.desc())
        .limit(1)
    )
    r2 = await db.execute(latest_file_stmt)
    latest_row = r2.first()
    if not latest_row:
        return {"total": 0, "vendors": [], "latest_time": None, "latest_filename": None}

    latest_file_id, latest_filename, record_count = latest_row

    if record_count == 0:
        return {"total": 0, "vendors": [], "latest_time": None, "latest_filename": latest_filename}

    # 仅查询最新文件的记录
    data_stmt = (
        select(ReportRecord.data)
        .where(ReportRecord.report_file_id == latest_file_id)
        .order_by(ReportRecord.id.desc())
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    records = [dict(row[0]) for row in rows]

    # 统计设备厂商（去重）
    vendors: list[str] = []
    seen_vendors = set()
    for rec in records:
        vendor = rec.get("设备厂商", "")
        if vendor and vendor not in seen_vendors:
            vendors.append(vendor)
            seen_vendors.add(vendor)

    return {
        "total": len(records),
        "vendors": vendors,
        "latest_time": None,  # 皮站故障清单没有时间字段
        "latest_filename": latest_filename,
    }


async def get_pisite_fault_detail(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """分页获取皮站故障横山详细数据：仅最新一份文件的5个字段数据"""
    stmt = select(ReportType).where(ReportType.name == "皮站故障清单")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": None}

    # 找到最新的 ReportFile
    latest_file_stmt = (
        select(ReportFile.id, ReportFile.filename, ReportFile.record_count)
        .where(ReportFile.report_type_id == report_type.id)
        .order_by(ReportFile.id.desc())
        .limit(1)
    )
    r2 = await db.execute(latest_file_stmt)
    latest_row = r2.first()
    if not latest_row:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": None}

    latest_file_id, latest_filename, record_count = latest_row

    if record_count == 0:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "latest_filename": latest_filename}

    # 仅查询最新文件的记录
    data_stmt = (
        select(ReportRecord.data, ReportFile.filename, ReportRecord.created_at)
        .join(ReportFile, ReportRecord.report_file_id == ReportFile.id)
        .where(ReportRecord.report_file_id == latest_file_id)
        .order_by(ReportRecord.id.desc())
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    all_records = []
    for row in rows:
        data, filename, created_at = row
        record = dict(data)
        record["_source_file"] = filename
        record["_created_at"] = created_at.isoformat() if created_at else ""
        all_records.append(record)

    total = len(all_records)

    # 分页
    offset = (page - 1) * page_size
    records = all_records[offset:offset + page_size]

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "latest_filename": latest_filename,
    }


async def get_report_records(
    report_type_id: int,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> Dict:
    """分页获取某报表类型的记录"""
    # 先查 report_type 是否存在
    stmt = select(ReportType).where(ReportType.id == report_type_id)
    r = await db.execute(stmt)
    rt = r.scalar_one_or_none()
    if not rt:
        return {"records": [], "total": 0, "page": page, "page_size": page_size}

    # 查记录（通过 report_files 关联）
    from sqlalchemy import join
    j = join(ReportRecord, ReportFile, ReportRecord.report_file_id == ReportFile.id)
    count_stmt = select(func.count(ReportRecord.id)).select_from(j).where(
        ReportFile.report_type_id == report_type_id
    )
    r2 = await db.execute(count_stmt)
    total = r2.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = (
        select(ReportRecord.data, ReportFile.filename, ReportRecord.created_at)
        .select_from(j)
        .where(ReportFile.report_type_id == report_type_id)
        .order_by(ReportRecord.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    records = []
    for row in rows:
        data, filename, created_at = row
        record = dict(data)
        record["_source_file"] = filename
        record["_created_at"] = created_at.isoformat() if created_at else ""
        records.append(record)

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
