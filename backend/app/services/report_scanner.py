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


# ── 接入层通报横山数据专用处理 ──

# 接入层通报保留字段（仅提取这6个字段）
ACCESS_LAYER_FAULT_FIELDS = [
    "接入层断纤链路",   # fiber_break_link
    "告警码名称",       # alarm_code_name
    "发生时间",         # occurrence_time
    "具体原因",         # specific_reason
    "是否影响业务",     # business_affected
    "故障历时",         # fault_duration
]

# 英文到中文映射
ACCESS_LAYER_FAULT_EN_TO_CN = {
    "fiber_break_link": "接入层断纤链路",
    "alarm_code_name": "告警码名称",
    "occurrence_time": "发生时间",
    "specific_reason": "具体原因",
    "business_affected": "是否影响业务",
    "fault_duration": "故障历时",
}


def _extract_date_from_filename(filename: str) -> Optional[str]:
    """从文件名中提取日期，用于排序确保最新文件在后。

    支持格式: 2026-06-04, 20260604, 2026年06月04日 等。
    返回 ISO 日期字符串 "YYYY-MM-DD"，失败返回 None。
    """
    patterns = [
        r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2020 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


# 接入层通报列关键字 → 英文字段名映射（用于包含匹配）
_ACCESS_LAYER_KEYWORD_MAP: list[tuple[str, str]] = [
    ("接入层断纤链路", "fiber_break_link"),
    ("告警码名称", "alarm_code_name"),
    ("发生时间", "occurrence_time"),
    ("具体原因", "specific_reason"),
    ("是否影响业务", "business_affected"),
    ("故障历时", "fault_duration"),
    ("县区", "district"),
    ("责任人", "responsible_person"),
]


def _parse_access_layer_fault_files(directory: str) -> list[dict]:
    """
    直接使用 openpyxl 解析所有"接入层通报"文件。
    关键字包含匹配表头 → 提取字段 → 过滤县区=="横山"。
    返回 [{"filename": str, "records": [dict]}, ...]
    """
    all_results: list[dict] = []

    # 递归查找匹配文件
    matching: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "接入层通报" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    # 排序：优先按文件名中的日期，回退到 mtime（旧的先处理，新的后处理 → 新文件 id 更大）
    def _sort_key(filepath: str) -> str:
        fname = os.path.basename(filepath)
        date_str = _extract_date_from_filename(fname)
        if date_str:
            return date_str
        # 回退：用 mtime 生成日期
        mtime = os.path.getmtime(filepath)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")

    matching.sort(key=_sort_key)

    for filepath in matching:
        filename = os.path.basename(filepath)
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            ws = wb.active

            # ── 步骤1：检测表头行 ──
            header_row_idx: Optional[int] = None
            col_map: dict[int, str] = {}  # 列索引 → 英文字段名

            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                matched = 0
                temp_map: dict[int, str] = {}
                for col_idx, cell in enumerate(row):
                    if cell is None:
                        continue
                    cell_str = str(cell).strip()
                    if not cell_str:
                        continue
                    # 关键字包含匹配：表头中"接入层断纤链路清单（2026-06-04）"包含"接入层断纤链路"
                    for kw, en_key in _ACCESS_LAYER_KEYWORD_MAP:
                        if len(kw) >= 2 and kw in cell_str:
                            temp_map[col_idx] = en_key
                            matched += 1
                            break

                if matched >= 4:  # 至少匹配 4 个关键字才认定是表头行（含 县区 共需 8 个）
                    header_row_idx = row_idx
                    col_map = temp_map
                    break

            if header_row_idx is None:
                logger.warning(f"接入层通报: {filename} 未检测到表头行")
                wb.close()
                continue

            logger.info(
                f"接入层通报: {filename} 表头行={header_row_idx}, 匹配列={list(col_map.values())}"
            )

            # ── 步骤2：提取数据行 ──
            filtered: list[dict] = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                if row_idx <= header_row_idx:
                    continue

                # 构建英文字段记录
                record: dict[str, str] = {}
                for col_idx, en_key in col_map.items():
                    val = ""
                    if col_idx < len(row) and row[col_idx] is not None:
                        val = str(row[col_idx]).strip()
                    record[en_key] = val

                # 过滤：县区 == 横山
                district = record.get("district", "")
                if district != "横山":
                    continue

                # 只保留 6 个指定字段，映射为中文名称
                clean: dict[str, str] = {}
                for en_key, cn_key in ACCESS_LAYER_FAULT_EN_TO_CN.items():
                    val = record.get(en_key, "")
                    clean[cn_key] = str(val) if val else ""
                filtered.append(clean)

            wb.close()

            all_results.append({
                "filename": filename,
                "records": filtered,
            })
            if filtered:
                logger.info(f"接入层通报横山: {filename} -> {len(filtered)} 条横山记录")
            else:
                logger.info(f"接入层通报横山: {filename} -> 0 条横山记录")

        except Exception as e:
            logger.error(f"解析接入层通报文件失败 {filename}: {e}", exc_info=True)

    return all_results


async def reparse_access_layer_fault(db: AsyncSession, directory: Optional[str] = None) -> dict:
    """
    重新解析接入层通报文件，仅保留横山区 6 个字段，更新数据库。
    删除旧的接入层通报 report_records 并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 获取或创建"接入层通报"报表类型
    stmt = select(ReportType).where(ReportType.name == "接入层通报")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="接入层通报", category="故障")
        db.add(report_type)
        await db.flush()

    # 删除旧的接入层通报记录（通过 report_files 关联删除 report_records）
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        from sqlalchemy import delete as _delete
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 在线程池中解析
    file_results = await asyncio.to_thread(_parse_access_layer_fault_files, directory)

    total_records = 0
    files_parsed = 0
    files_skipped = 0
    all_columns = set(ACCESS_LAYER_FAULT_FIELDS)

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


async def get_access_layer_fault_summary(db: AsyncSession) -> dict:
    """获取接入层通报横山数据概要：故障总数 + 影响业务数 + 不影响业务数 + 告警码名称列表"""
    stmt = select(ReportType).where(ReportType.name == "接入层通报")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        return {"total": 0, "business_affected": 0, "business_unaffected": 0, "alarm_code_names": [], "latest_time": None, "latest_filename": None}

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
        return {"total": 0, "business_affected": 0, "business_unaffected": 0, "alarm_code_names": [], "latest_time": None, "latest_filename": None}

    latest_file_id, latest_filename, record_count = latest_row

    if record_count == 0:
        return {"total": 0, "business_affected": 0, "business_unaffected": 0, "alarm_code_names": [], "latest_time": None, "latest_filename": latest_filename}

    # 仅查询最新文件的记录
    data_stmt = (
        select(ReportRecord.data)
        .where(ReportRecord.report_file_id == latest_file_id)
        .order_by(ReportRecord.id.desc())
    )
    r3 = await db.execute(data_stmt)
    rows = r3.all()

    records = [dict(row[0]) for row in rows]

    business_affected = 0
    business_unaffected = 0
    alarm_code_names: list[str] = []
    seen_names = set()

    for rec in records:
        # 统计影响业务 / 不影响业务
        affected = str(rec.get("是否影响业务", "")).strip()
        if affected == "是":
            business_affected += 1
        elif affected == "否":
            business_unaffected += 1

        # 收集告警码名称（去重）
        name = rec.get("告警码名称", "")
        if name and name not in seen_names:
            alarm_code_names.append(name)
            seen_names.add(name)

    latest_time = records[0].get("发生时间", "") if records else None

    return {
        "total": len(records),
        "business_affected": business_affected,
        "business_unaffected": business_unaffected,
        "alarm_code_names": alarm_code_names,
        "latest_time": latest_time,
        "latest_filename": latest_filename,
    }


async def get_access_layer_fault_detail(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """分页获取接入层通报横山详细数据：仅最新一份文件的6个字段数据"""
    stmt = select(ReportType).where(ReportType.name == "接入层通报")
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


# ── 企宽装机通报横山数据专用处理 ──

def _parse_enterprise_broadband_files(directory: str) -> dict:
    """
    解析最新的"企宽装机通报"文件：
    1. 从"移动汇报"sheet 提取横山汇总指标
    2. 从"积压"sheet 提取横山积压清单（计算装机历时）
    返回 {"summary": dict, "backlog": [dict], "filename": str, "report_date": str}
    """
    from datetime import datetime as _dt

    # 找到最新的企宽装机通报文件
    matching: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "企宽装机通报" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    if not matching:
        return {"summary": None, "backlog": [], "filename": None, "report_date": None}

    # 按修改时间排序，取最新
    matching.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    latest_file = matching[0]
    filename = os.path.basename(latest_file)

    try:
        wb = openpyxl.load_workbook(latest_file, read_only=True, data_only=True)

        # ── 1. 解析"移动汇报"sheet ──
        summary = None
        report_date = None
        if "移动汇报" in wb.sheetnames:
            ws = wb["移动汇报"]
            rows_data = list(ws.iter_rows(values_only=True))

            # 提取标题中的日期
            if rows_data and rows_data[0][0]:
                title = str(rows_data[0][0])
                date_match = re.search(r'(\d+)月(\d+)日', title)
                if date_match:
                    now = _dt.now()
                    report_date = f"{now.year}-{date_match.group(1).zfill(2)}-{date_match.group(2).zfill(2)}"

            # 查找横山行（数据从第4行开始，列: 0=县区, 1-10=指标值）
            for row in rows_data[4:]:
                if row[0] and str(row[0]).strip() == "横山县":
                    summary = {
                        "district": "横山",
                        "month_accept": str(row[1]) if row[1] is not None else "",
                        "month_archive": str(row[2]) if row[2] is not None else "",
                        "month_success_rate": str(row[3]) if row[3] is not None else "",
                        "month_reject": str(row[4]) if row[4] is not None else "",
                        "total_backlog": str(row[5]) if row[5] is not None else "",
                        "day_accept": str(row[6]) if row[6] is not None else "",
                        "day_archive": str(row[7]) if row[7] is not None else "",
                        "day_success_rate": str(row[8]) if row[8] is not None else "",
                        "day_reject": str(row[9]) if row[9] is not None else "",
                        "day_backlog": str(row[10]) if row[10] is not None else "",
                    }
                    break

        # ── 2. 解析"积压"sheet ──
        backlog_records: list[dict] = []
        if "积压" in wb.sheetnames:
            ws2 = wb["积压"]
            # 流式读取表头（仅第一行），避免 list() 加载百万行导致 OOM
            row_iter = ws2.iter_rows(values_only=True)
            try:
                header_row = next(row_iter)
            except StopIteration:
                header_row = ()

            if not header_row:
                wb.close()
                return {"summary": summary, "backlog": [], "filename": filename, "report_date": report_date}

            col_map: dict[str, int] = {}
            target_fields = ["所属区县", "宽带账号", "施工地址", "施工人姓名",
                             "受理时间", "到装维时间", "完成时限", "用户品牌"]
            for target in target_fields:
                for idx, cell in enumerate(header_row):
                    if cell and str(cell).strip() == target:
                        col_map[target] = idx
                        break

            # 确保所有必要字段都找到了
            missing = [f for f in target_fields if f not in col_map]
            if missing:
                logger.warning(f"企宽装机通报积压sheet缺少字段: {missing}")
                wb.close()
                return {"summary": summary, "backlog": [], "filename": filename, "report_date": report_date}

            max_col_idx = max(col_map.values())
            # 流式遍历剩余数据行（不加载全量到内存）
            for row in row_iter:
                if not row or len(row) <= max_col_idx:
                    continue

                district_val = str(row[col_map.get("所属区县")]).strip() if col_map.get("所属区县") is not None and row[col_map["所属区县"]] else ""
                if district_val != "横山县":
                    continue

                # 计算装机历时(h) = 完成时限 - 到装维时间
                install_duration = ""
                deadline_str = str(row[col_map["完成时限"]]) if "完成时限" in col_map and row[col_map["完成时限"]] else ""
                to_install_str = str(row[col_map["到装维时间"]]) if "到装维时间" in col_map and row[col_map["到装维时间"]] else ""

                if deadline_str and to_install_str:
                    try:
                        deadline_dt = _dt.strptime(deadline_str[:19], "%Y-%m-%d %H:%M:%S")
                        to_install_dt = _dt.strptime(to_install_str[:19], "%Y-%m-%d %H:%M:%S")
                        diff = deadline_dt - to_install_dt
                        hours = diff.total_seconds() / 3600.0
                        install_duration = f"{hours:.2f}"
                    except (ValueError, TypeError):
                        install_duration = ""

                record = {
                    "district": district_val,
                    "account": str(row[col_map["宽带账号"]]) if "宽带账号" in col_map and row[col_map["宽带账号"]] else "",
                    "address": str(row[col_map["施工地址"]]) if "施工地址" in col_map and row[col_map["施工地址"]] else "",
                    "worker_name": str(row[col_map["施工人姓名"]]) if "施工人姓名" in col_map and row[col_map["施工人姓名"]] else "",
                    "accept_time": str(row[col_map["受理时间"]]) if "受理时间" in col_map and row[col_map["受理时间"]] else "",
                    "to_install_time": to_install_str,
                    "deadline": deadline_str,
                    "install_duration_hours": install_duration,
                    "user_brand": str(row[col_map["用户品牌"]]) if "用户品牌" in col_map and row[col_map["用户品牌"]] else "",
                }
                backlog_records.append(record)

            logger.info(f"企宽装机通报横山积压: {filename} -> {len(backlog_records)} 条")

        wb.close()
        return {
            "summary": summary,
            "backlog": backlog_records,
            "filename": filename,
            "report_date": report_date,
        }

    except Exception as e:
        logger.error(f"解析企宽装机通报失败 {filename}: {e}", exc_info=True)
        return {"summary": None, "backlog": [], "filename": filename, "report_date": None}


async def reparse_enterprise_broadband(db: AsyncSession, directory: Optional[str] = None) -> dict:
    """
    重新解析企宽装机通报文件，提取横山汇总指标和积压清单，更新数据库。
    删除旧数据并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 在线程池中解析
    result = await asyncio.to_thread(_parse_enterprise_broadband_files, directory)

    # ── 写入汇总表 ──
    # 删除旧汇总数据
    from app.core.models import EnterpriseBroadbandSummary, EnterpriseBroadbandBacklog
    from sqlalchemy import delete as _delete
    await db.execute(_delete(EnterpriseBroadbandSummary))
    await db.execute(_delete(EnterpriseBroadbandBacklog))

    summary_count = 0
    if result["summary"]:
        s = result["summary"]
        ebs = EnterpriseBroadbandSummary(
            report_date=result["report_date"] or "",
            district=s["district"],
            month_accept=s["month_accept"],
            month_archive=s["month_archive"],
            month_success_rate=s["month_success_rate"],
            month_reject=s["month_reject"],
            total_backlog=s["total_backlog"],
            day_accept=s["day_accept"],
            day_archive=s["day_archive"],
            day_success_rate=s["day_success_rate"],
            day_reject=s["day_reject"],
            day_backlog=s["day_backlog"],
        )
        db.add(ebs)
        summary_count = 1

    # ── 写入积压清单 ──
    # 先获取或创建"企宽装机通报"报表类型用于关联 ReportFile
    stmt = select(ReportType).where(ReportType.name == "企宽装机通报")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="企宽装机通报", category="装维生产")
        db.add(report_type)
        await db.flush()

    # 删除旧的企宽装机通报 report_files/report_records
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 创建 ReportFile（用于积压清单关联）
    report_file = ReportFile(
        report_type_id=report_type.id,
        filename=result["filename"] or "",
        file_path=os.path.join(directory, result["filename"] or ""),
        parse_status="parsed",
        record_count=len(result["backlog"]),
    )
    db.add(report_file)
    await db.flush()

    backlog_count = 0
    for rec in result["backlog"]:
        ebb = EnterpriseBroadbandBacklog(
            report_file_id=report_file.id,
            district=rec["district"],
            account=rec["account"],
            address=rec["address"],
            worker_name=rec["worker_name"],
            accept_time=rec["accept_time"],
            to_install_time=rec["to_install_time"],
            deadline=rec["deadline"],
            install_duration_hours=rec["install_duration_hours"],
            user_brand=rec["user_brand"],
        )
        db.add(ebb)
        backlog_count += 1

    await db.commit()

    return {
        "summary_parsed": summary_count,
        "backlog_count": backlog_count,
        "filename": result["filename"],
        "report_date": result["report_date"],
    }


async def get_enterprise_broadband_summary(db: AsyncSession) -> dict:
    """获取企宽装机通报横山卡片指标"""
    from app.core.models import EnterpriseBroadbandSummary
    stmt = select(EnterpriseBroadbandSummary).order_by(EnterpriseBroadbandSummary.id.desc()).limit(1)
    r = await db.execute(stmt)
    row = r.scalar_one_or_none()
    if not row:
        return {
            "district": "横山",
            "month_accept": "", "month_archive": "", "month_success_rate": "",
            "month_reject": "", "total_backlog": "",
            "day_accept": "", "day_archive": "", "day_success_rate": "",
            "day_reject": "", "day_backlog": "",
            "report_date": "",
        }
    return {
        "district": row.district,
        "month_accept": row.month_accept,
        "month_archive": row.month_archive,
        "month_success_rate": row.month_success_rate,
        "month_reject": row.month_reject,
        "total_backlog": row.total_backlog,
        "day_accept": row.day_accept,
        "day_archive": row.day_archive,
        "day_success_rate": row.day_success_rate,
        "day_reject": row.day_reject,
        "day_backlog": row.day_backlog,
        "report_date": row.report_date,
    }


async def get_enterprise_broadband_backlog(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """分页获取企宽装机通报横山积压清单"""
    from app.core.models import EnterpriseBroadbandBacklog
    from sqlalchemy import func as _func

    count_stmt = select(_func.count(EnterpriseBroadbandBacklog.id))
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = (
        select(EnterpriseBroadbandBacklog)
        .order_by(EnterpriseBroadbandBacklog.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    records = []
    for row in rows:
        records.append({
            "id": row.id,
            "district": row.district,
            "account": row.account,
            "address": row.address,
            "worker_name": row.worker_name,
            "accept_time": row.accept_time,
            "to_install_time": row.to_install_time,
            "deadline": row.deadline,
            "install_duration_hours": row.install_duration_hours,
            "user_brand": row.user_brand,
        })

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
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
