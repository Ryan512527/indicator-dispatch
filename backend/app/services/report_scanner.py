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


# ── 日报横山数据专用处理 ──

# 两类指标保留字段
TWO_CAT_FIELDS = [
    "积压总量",      # backlog_total
    "家宽转化率",    # broadband_rate
    "FTTR转化率",    # fttr_rate
    "总装机转化率",  # total_rate
]

# 五类指标保留字段
FIVE_CAT_FIELDS = [
    "积压总量",      # backlog_total
    "家宽转化率",    # broadband_rate
    "智能组网",      # smart_network
    "平安乡村",      # safe_village
    "FTTR转化率",    # fttr_rate
    "总装机转化率",  # total_rate
]

# 宽带积压保留字段
BACKLOG_FIELDS = [
    "所属区县",
    "覆盖场景",
    "宽带账号",
    "服务",
    "施工地址",
    "施工人姓名",
    "工单状态",
    "受理时间",
    "到装维时间",
    "完成时限",
    "积压时长h",
    "用户品牌",
]


def _parse_daily_report_files(directory: str) -> dict:
    """
    解析所有"日报"文件，提取横山数据：
    1. "两类" sheet → 两类装机成功率概况
    2. "五类" sheet → 五类装机成功率概况
    3. "宽带积压" sheet → 装机积压清单（含计算装机历时）
    使用 openpyxl(read_only=True) + 迭代器流式读取。
    返回 {"summary": dict, "backlog": [dict], "filename": str, "report_date": str}
    """
    from datetime import datetime as _dt

    # 找到最新的日报文件
    matching: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "日报" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    if not matching:
        return {"summary": None, "backlog": [], "filename": None, "report_date": None}

    # 按修改时间排序，取最新
    matching.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    latest_file = matching[0]
    filename = os.path.basename(latest_file)

    # 尝试从文件名提取日期
    report_date = None
    date_match = re.search(r'(\d{4})[-年](\d{1,2})[-月](\d{1,2})', filename)
    if date_match:
        report_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
    else:
        report_date = _dt.now().strftime("%Y-%m-%d")

    try:
        wb = openpyxl.load_workbook(latest_file, read_only=True, data_only=True)
        summary: dict = {}
        backlog_records: list[dict] = []

        # ── 1. 解析"两类" sheet ──
        if "两类" in wb.sheetnames:
            ws = wb["两类"]
            summary["two_cat"] = _parse_category_sheet(ws, "两类", TWO_CAT_FIELDS)
        else:
            logger.warning(f"日报文件 {filename} 缺少'两类'sheet")

        # ── 2. 解析"五类" sheet ──
        if "五类" in wb.sheetnames:
            ws = wb["五类"]
            summary["five_cat"] = _parse_category_sheet(ws, "五类", FIVE_CAT_FIELDS)
        else:
            logger.warning(f"日报文件 {filename} 缺少'五类'sheet")

        # ── 3. 解析"宽带积压" sheet ──
        if "宽带积压" in wb.sheetnames:
            ws = wb["宽带积压"]
            backlog_records = _parse_backlog_sheet(ws, filename, source_label="宽带积压")
        else:
            logger.warning(f"日报文件 {filename} 缺少'宽带积压'sheet")

        # ── 4. 解析"FTTR积压" sheet ──
        if "FTTR积压" in wb.sheetnames:
            ws = wb["FTTR积压"]
            fttr_records = _parse_backlog_sheet(ws, filename, source_label="FTTR积压")
            backlog_records.extend(fttr_records)
        else:
            logger.warning(f"日报文件 {filename} 缺少'FTTR积压'sheet")

        wb.close()

        logger.info(
            f"日报横山: {filename} -> 两类={summary.get('two_cat')}, "
            f"五类={summary.get('five_cat')}, 积压={len(backlog_records)} 条"
        )

        return {
            "summary": summary,
            "backlog": backlog_records,
            "filename": filename,
            "report_date": report_date,
        }

    except Exception as e:
        logger.error(f"解析日报文件失败 {filename}: {e}", exc_info=True)
        return {"summary": None, "backlog": [], "filename": filename, "report_date": report_date}


def _parse_category_sheet(ws, sheet_label: str, target_fields: list[str]) -> dict | None:
    """
    解析"两类"/"五类"sheet，定位横山行并提取指标值。
    
    策略：流式遍历行，在第一列中查找"横山"或"横山县"。
    表头行通过标题行（包含"两类"/"五类"关键词）定位。
    找到横山行后，按目标字段顺序提取对应列的值。
    """
    try:
        rows_data = list(ws.iter_rows(values_only=True))
    except Exception:
        # 某些 read_only 模式下无法 list，回退逐行读取
        rows_data = []
        for row in ws.iter_rows(values_only=True):
            rows_data.append(row)

    if len(rows_data) < 2:
        return None

    # 查找横山行：扫描全表，找到第一列是"横山"或"横山县"的行，同时用该行上方最近的非空行作为可能的表头
    hengshan_row_idx = None
    hengshan_row = None
    header_row_idx = None

    for idx, row in enumerate(rows_data):
        first_cell = str(row[0]).strip() if row and row[0] else ""
        if first_cell in ("横山", "横山县"):
            hengshan_row_idx = idx
            hengshan_row = row
            break

    if hengshan_row_idx is None:
        logger.info(f"日报 {sheet_label} sheet 未找到横山行")
        return None

    # 查找表头行：从第1行开始（跳过标题行0），向横山行方向搜索包含指标关键字的行
    for idx in range(1, hengshan_row_idx):
        row = rows_data[idx]
        row_text = " ".join(str(c) for c in row if c)
        # 检查是否包含"积压总量"或"转化率"等指标关键字
        if any(kw in row_text for kw in ["积压总量", "转化率", "装机"]):
            header_row_idx = idx
            break

    result: dict[str, str] = {}
    for i, field in enumerate(target_fields):
        result[field] = ""

    if hengshan_row is None:
        return result

    # 如果有表头行，按表头列名匹配
    if header_row_idx is not None:
        header_row = rows_data[header_row_idx]
        for i, field in enumerate(target_fields):
            for col_idx, header_cell in enumerate(header_row):
                if header_cell and field in str(header_cell).strip():
                    val = hengshan_row[col_idx] if col_idx < len(hengshan_row) else ""
                    result[field] = str(val).strip() if val is not None else ""
                    break

    # 如果表头匹配失败，回退：按横山行数据顺序填充（跳过第一列区县名）
    if all(v == "" for v in result.values()):
        for i, field in enumerate(target_fields):
            col_idx = i + 1  # 跳过第一列（区县名）
            if col_idx < len(hengshan_row):
                val = hengshan_row[col_idx]
                result[field] = str(val).strip() if val is not None else ""

    return result


def _parse_backlog_sheet(ws, filename: str, source_label: str = "宽带积压") -> list[dict]:
    """
    解析"宽带积压"或"FTTR积压"sheet，流式读取，过滤横山区数据。
    计算装机历时(h) = 完成时限 - 到装维时间。
    返回 [record, ...]，每条记录带 data_source 标记。
    """
    from datetime import datetime as _dt

    row_iter = ws.iter_rows(values_only=True)

    # 读取前几行找表头（表头通常在前5行内）
    header_row = None
    header_rows_buf: list[tuple] = []
    for i in range(10):
        try:
            r = next(row_iter)
            header_rows_buf.append(r)
            # 检查是否包含关键字段
            row_text = " ".join(str(c) for c in r if c)
            if any(kw in row_text for kw in ["宽带账号", "所属区县", "施工地址"]):
                header_row = r
                break
        except StopIteration:
            break

    if header_row is None:
        logger.warning(f"日报{source_label} sheet 未检测到表头行: {filename}")
        return []

    # 建立列映射（字段名匹配，>=2字符防止单字符误匹配）
    col_map: dict[str, int] = {}
    
    # 先处理需要语义回退的特殊字段
    _SEMANTIC_ALIASES = {
        "用户品牌": "客户等级",
    }
    
    for idx, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_str = str(cell).strip()
        for field in BACKLOG_FIELDS:
            if len(field) >= 2 and field in cell_str:
                col_map[field] = idx
                break
    
    # 语义回退：如果原始字段没匹配到，用别名再试
    for field, alias in _SEMANTIC_ALIASES.items():
        if field not in col_map:
            for idx, cell in enumerate(header_row):
                if cell is None:
                    continue
                cell_str = str(cell).strip()
                if alias in cell_str:
                    col_map[field] = idx
                    logger.info(f"日报{source_label}: '{field}' 语义回退到 '{alias}' col={idx}")
                    break

    # 验证关键字段
    missing = [f for f in ["所属区县", "覆盖场景", "宽带账号"] if f not in col_map]
    if missing:
        logger.warning(f"日报{source_label} sheet 缺少关键字段: {missing}")
        return []

    # "积压时长h" 特殊处理：表头单元格为合并残留（None或数字），
    # 查找 col1 位置（通常是积压时长数值列，值为数字型小时数）
    if "积压时长h" not in col_map:
        # 检查 col1：如果表头为 None/数字 且数据行为数值，则认定为积压时长列
        if len(header_row) > 1 and (header_row[1] is None or isinstance(header_row[1], (int, float))):
            col_map["积压时长h"] = 1
            logger.info(f"日报{source_label}: '积压时长h' 通过 col1 (合并单元格) 检测到")
        elif source_label == "FTTR积压" and len(header_row) > 2:
            # FTTR积压特殊处理：col1为积压天数（小数），col2为积压时长h，
            # col3为积压时长标签（如"48小时以上"）。优先使用col2。
            col_map["积压时长h"] = 2
            logger.info(f"日报{source_label}: '积压时长h' 通过 col2 (FTTR合并单元格回退) 检测到")

    max_col_idx = max(col_map.values())

    # 流式遍历数据行，过滤横山 + 家庭场景
    backlog_records: list[dict] = []
    for row in row_iter:
        if not row or len(row) <= max_col_idx:
            continue

        # 过滤横山
        district_val = ""
        if "所属区县" in col_map and row[col_map["所属区县"]]:
            district_val = str(row[col_map["所属区县"]]).strip()

        if district_val != "横山" and district_val != "横山县":
            continue

        # 过滤家庭场景
        scene_val = ""
        if "覆盖场景" in col_map and row[col_map["覆盖场景"]]:
            scene_val = str(row[col_map["覆盖场景"]]).strip()

        if scene_val != "家庭场景":
            continue

        # 提取字段
        def _get(field: str) -> str:
            if field in col_map and col_map[field] < len(row) and row[col_map[field]] is not None:
                val = row[col_map[field]]
                if isinstance(val, _dt):
                    return val.strftime("%Y-%m-%d %H:%M:%S")
                return str(val).strip()
            return ""

        # 计算装机历时(h)
        install_duration = ""
        deadline_str = _get("完成时限")
        to_install_str = _get("到装维时间")

        if deadline_str and to_install_str:
            # 尝试多种日期格式
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
                        "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M",
                        "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    dl = deadline_str.strip()
                    ti = to_install_str.strip()
                    deadline_dt = _dt.strptime(dl, fmt)
                    to_install_dt = _dt.strptime(ti, fmt)
                    diff = deadline_dt - to_install_dt
                    hours = diff.total_seconds() / 3600.0
                    install_duration = f"{hours:.2f}"
                    break
                except (ValueError, TypeError):
                    continue

        # 计算积压时长提醒标签
        duration_warning = ""
        try:
            duration_h = float(install_duration) if install_duration else 0
            if duration_h > 48:
                duration_warning = "超48h"
            elif duration_h > 24:
                duration_warning = "超24h"
            elif duration_h > 8:
                duration_warning = "超8h"
        except (ValueError, TypeError):
            pass

        record = {
            "所属区县": _get("所属区县"),
            "覆盖场景": _get("覆盖场景"),
            "宽带账号": _get("宽带账号"),
            "服务": _get("服务"),
            "施工地址": _get("施工地址"),
            "施工人姓名": _get("施工人姓名"),
            "工单状态": _get("工单状态"),
            "受理时间": _get("受理时间"),
            "到装维时间": _get("到装维时间"),
            "完成时限": _get("完成时限"),
            "积压时长h": _get("积压时长h"),
            "装机历时(h)": install_duration,
            "时长提醒": duration_warning,
            "用户品牌": _get("用户品牌"),
            "数据来源": source_label,
        }

        backlog_records.append(record)

    logger.info(f"日报{source_label}横山: {filename} -> {len(backlog_records)} 条")
    return backlog_records


async def reparse_daily_report(db: AsyncSession, directory: Optional[str] = None) -> dict:
    """
    重新解析日报文件，提取横山两类/五类概况 + 宽带积压清单，更新数据库。
    删除旧数据并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 在线程池中解析
    result = await asyncio.to_thread(_parse_daily_report_files, directory)

    # 导入模型
    from app.core.models import DailyReportSummary, DailyReportBacklog
    from sqlalchemy import delete as _delete

    # 删除旧数据
    await db.execute(_delete(DailyReportSummary))
    await db.execute(_delete(DailyReportBacklog))

    # ── 写入汇总表 ──
    summary_count = 0
    if result["summary"]:
        s = result["summary"]
        two = s.get("two_cat") or {}
        five = s.get("five_cat") or {}

        drs = DailyReportSummary(
            report_date=result["report_date"] or "",
            two_cat_backlog_total=two.get("积压总量", ""),
            two_cat_broadband_rate=two.get("家宽转化率", ""),
            two_cat_fttr_rate=two.get("FTTR转化率", ""),
            two_cat_total_rate=two.get("总装机转化率", ""),
            five_cat_backlog_total=five.get("积压总量", ""),
            five_cat_broadband_rate=five.get("家宽转化率", ""),
            five_cat_smart_network=five.get("智能组网", ""),
            five_cat_safe_village=five.get("平安乡村", ""),
            five_cat_fttr_rate=five.get("FTTR转化率", ""),
            five_cat_total_rate=five.get("总装机转化率", ""),
        )
        db.add(drs)
        summary_count = 1

    # ── 获取或创建"日报"报表类型 ──
    stmt = select(ReportType).where(ReportType.name == "日报")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="日报", category="装维生产")
        db.add(report_type)
        await db.flush()

    # 删除旧的日报 report_files/report_records
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 创建 ReportFile
    report_file = ReportFile(
        report_type_id=report_type.id,
        filename=result["filename"] or "",
        file_path=os.path.join(directory, result["filename"] or ""),
        parse_status="parsed",
        record_count=len(result["backlog"]),
    )
    db.add(report_file)
    await db.flush()

    # ── 写入积压清单 ──
    backlog_count = 0
    for rec in result["backlog"]:
        drb = DailyReportBacklog(
            report_file_id=report_file.id,
            district=rec.get("所属区县", ""),
            coverage_scenario=rec.get("覆盖场景", ""),
            account=rec.get("宽带账号", ""),
            service=rec.get("服务", ""),
            address=rec.get("施工地址", ""),
            worker_name=rec.get("施工人姓名", ""),
            order_status=rec.get("工单状态", ""),
            accept_time=rec.get("受理时间", ""),
            to_install_time=rec.get("到装维时间", ""),
            deadline=rec.get("完成时限", ""),
            backlog_hours=rec.get("积压时长h", ""),
            install_duration_hours=rec.get("装机历时(h)", ""),
            user_brand=rec.get("用户品牌", ""),
            data_source=rec.get("数据来源", ""),
        )
        db.add(drb)
        backlog_count += 1

    # 更新 column_hint
    report_type.column_hint = BACKLOG_FIELDS.copy()
    report_type.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "summary_parsed": summary_count,
        "backlog_count": backlog_count,
        "filename": result["filename"],
        "report_date": result["report_date"],
    }


async def get_daily_report_summary(db: AsyncSession) -> dict:
    """获取日报横山卡片汇总指标（两类+五类装机成功率）"""
    from app.core.models import DailyReportSummary

    stmt = select(DailyReportSummary).order_by(DailyReportSummary.id.desc()).limit(1)
    r = await db.execute(stmt)
    row = r.scalar_one_or_none()

    if not row:
        return {
            "report_date": "",
            "two_cat": {"积压总量": "", "家宽转化率": "", "FTTR转化率": "", "总装机转化率": ""},
            "five_cat": {"积压总量": "", "家宽转化率": "", "智能组网": "", "平安乡村": "", "FTTR转化率": "", "总装机转化率": ""},
        }

    return {
        "report_date": row.report_date,
        "two_cat": {
            "积压总量": row.two_cat_backlog_total,
            "家宽转化率": row.two_cat_broadband_rate,
            "FTTR转化率": row.two_cat_fttr_rate,
            "总装机转化率": row.two_cat_total_rate,
        },
        "five_cat": {
            "积压总量": row.five_cat_backlog_total,
            "家宽转化率": row.five_cat_broadband_rate,
            "智能组网": row.five_cat_smart_network,
            "平安乡村": row.five_cat_safe_village,
            "FTTR转化率": row.five_cat_fttr_rate,
            "总装机转化率": row.five_cat_total_rate,
        },
    }


async def get_daily_report_backlog(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """分页获取日报横山装机积压清单"""
    from app.core.models import DailyReportBacklog
    from sqlalchemy import func as _func

    count_stmt = select(_func.count(DailyReportBacklog.id))
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    offset = (page - 1) * page_size
    data_stmt = (
        select(DailyReportBacklog)
        .order_by(DailyReportBacklog.id.asc())
        .offset(offset)
        .limit(page_size)
    )
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    records = []
    for row in rows:
        # 计算时长提醒标签
        duration_warning = ""
        try:
            duration_h = float(row.install_duration_hours) if row.install_duration_hours else 0
            if duration_h > 48:
                duration_warning = "超48h"
            elif duration_h > 24:
                duration_warning = "超24h"
            elif duration_h > 8:
                duration_warning = "超8h"
        except (ValueError, TypeError):
            pass

        records.append({
            "id": row.id,
            "所属区县": row.district,
            "覆盖场景": row.coverage_scenario,
            "宽带账号": row.account,
            "服务": row.service,
            "施工地址": row.address,
            "施工人姓名": row.worker_name,
            "工单状态": row.order_status,
            "受理时间": row.accept_time,
            "到装维时间": row.to_install_time,
            "完成时限": row.deadline,
            "积压时长h": row.backlog_hours,
            "装机历时(h)": row.install_duration_hours,
            "时长提醒": duration_warning,
            "用户品牌": row.user_brand,
            "数据来源": row.data_source,
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


# ── 全市装维工作量统计横山数据专用处理 ──

# "汇总"sheet 目标字段关键字
_CITY_WORKLOAD_SUMMARY_KEYWORDS = {
    "人员数量": "total_staff",
    "有工作量人数": "working_staff",
    "请假人数": "leave_staff",
    "无工作量占比": "no_work_ratio",
}

# "到个人"sheet 目标字段
_CITY_WORKLOAD_WORKER_FIELDS = [
    "姓名", "区域", "装移拆", "投诉", "LAN口", "巡检",
    "一户一案", "质差弱光", "小计",
]


def _parse_city_workload_files(directory: str) -> dict:
    """
    解析最新的"全市装维工作量统计"文件：
    1. 从"汇总"sheet 提取横山汇总指标
    2. 从"到个人"sheet 提取横山装维人员工作量明细
    返回 {"summary": dict, "workers": [dict], "filename": str, "report_date": str}
    """
    from datetime import datetime as _dt

    # 找到最新的全市装维工作量统计文件
    matching: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.startswith("~$") or f.startswith("."):
                continue
            if "全市装维工作量统计" in f and f.lower().endswith((".xlsx", ".xls")):
                matching.append(os.path.join(root, f))

    if not matching:
        return {"summary": None, "workers": [], "filename": None, "report_date": None}

    # 按修改时间排序，取最新
    matching.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    latest_file = matching[0]
    filename = os.path.basename(latest_file)

    # 尝试从文件名提取日期
    report_date = None
    date_match = re.search(r'(\d{4})[-年](\d{1,2})[-月](\d{1,2})', filename)
    if date_match:
        report_date = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
    else:
        report_date = _dt.now().strftime("%Y-%m-%d")

    try:
        wb = openpyxl.load_workbook(latest_file, read_only=True, data_only=True)

        # ── 1. 解析"汇总"sheet ──
        summary = None
        if "汇总" in wb.sheetnames:
            ws = wb["汇总"]
            rows_data = list(ws.iter_rows(values_only=True))

            # 表头跨两行（Row1=分组标题, Row2=子标题），需要合并扫描
            # 构建 keyword -> col_index 的映射（扫描所有header行）
            keyword_col_map: dict[str, int] = {}
            hengshan_row_idx = None
            hengshan_row = None

            for idx, row in enumerate(rows_data[:5]):  # 只扫描前5行作为header区域
                row_text = " ".join(str(c) for c in row if c)
                for col_i, cell in enumerate(row):
                    if cell is None:
                        continue
                    cell_str = str(cell).strip()
                    for kw in _CITY_WORKLOAD_SUMMARY_KEYWORDS:
                        if kw in cell_str and kw not in keyword_col_map:
                            keyword_col_map[kw] = col_i

                # 同时检测横山数据行
                if "横山" in row_text or "横山县" in row_text:
                    hengshan_row_idx = idx
                    hengshan_row = row
                if "合计" in row_text:
                    break  # 合计行是数据行，不是header

            # 继续扫描剩余数据行找横山
            if hengshan_row is None:
                for idx in range(5, len(rows_data)):
                    row = rows_data[idx]
                    row_text = " ".join(str(c) for c in row if c)
                    if "横山" in row_text or "横山县" in row_text:
                        hengshan_row_idx = idx
                        hengshan_row = row
                        break

            # 提取数据
            if keyword_col_map and hengshan_row is not None:
                summary = {
                    "district": "横山",
                    "total_staff": "",
                    "working_staff": "",
                    "leave_staff": "",
                    "no_work_ratio": "",
                }
                for kw, key in _CITY_WORKLOAD_SUMMARY_KEYWORDS.items():
                    col_idx = keyword_col_map.get(kw)
                    if col_idx is not None and col_idx < len(hengshan_row):
                        val = hengshan_row[col_idx]
                        if val is not None:
                            val_str = str(val).strip()
                            # 百分比格式化
                            if "占比" in kw or "率" in kw:
                                try:
                                    pct = float(val_str)
                                    if pct < 1:
                                        val_str = f"{pct * 100:.1f}%"
                                    else:
                                        val_str = f"{pct:.1f}%"
                                except (ValueError, TypeError):
                                    pass
                            summary[key] = val_str

            if summary:
                logger.info(f"全市装维工作量统计横山汇总: {filename} -> {summary}")
            else:
                logger.warning(f"全市装维工作量统计: {filename} 汇总sheet未找到横山数据")
        else:
            logger.warning(f"全市装维工作量统计: {filename} 缺少'汇总'sheet")

        # ── 2. 解析"到个人"sheet ──
        workers: list[dict] = []
        if "到个人" in wb.sheetnames:
            ws2 = wb["到个人"]
            rows_data2 = list(ws2.iter_rows(values_only=True))

            # 表头结构: Row0=标题, Row1=分组标题(县区/姓名/累计积压量/当日工作量统计), Row2=子标题(详细列名)
            # 跳过Row0(标题行)，组合Row1+Row2来理解列含义
            if len(rows_data2) >= 3:
                row1 = rows_data2[1]  # 分组标题: 县区, 姓名, 账号, 岗位, 网格, 累计积压量, ..., 当日工作量统计, ...
                row2 = rows_data2[2]  # 子标题: 装移拆, 投诉, LAN口（到个人）, ...

                # 建立列映射
                name_col = None
                area_col = None
                grid_col = None
                # 工作类型 -> {"backlog": col_idx, "today": col_idx}
                wt_col_map: dict[str, dict[str, int]] = {}
                # 记录"累计积压量"组和"当日工作量统计"组的起始列
                backlog_group_start = None
                today_group_start = None

                # 第一遍：从Row1找到区县、姓名、以及"累计积压量"和"当日工作量统计"分组起始列
                for idx, cell in enumerate(row1):
                    if cell is None:
                        continue
                    cell_str = str(cell).strip()
                    if cell_str == "县区":
                        area_col = idx
                    elif cell_str == "姓名":
                        name_col = idx
                    elif cell_str == "网格":
                        grid_col = idx
                    elif "累计积压量" in cell_str or "积压量" in cell_str:
                        backlog_group_start = idx
                    elif "当日工作量" in cell_str or "当日工作" in cell_str:
                        today_group_start = idx

                # 如果没找到姓名或区域，尝试从Row2找
                if name_col is None or area_col is None:
                    for idx, cell in enumerate(row2):
                        if cell is None:
                            continue
                        cell_str = str(cell).strip()
                        if name_col is None and cell_str == "姓名":
                            name_col = idx
                        if area_col is None and cell_str == "县区":
                            area_col = idx

                # 第二遍：从Row2找到各工作类型的积压/当日列
                # 注意：排除"小计"和"请假"，它们不是真实工作类型
                # 积压工作类型映射（Row2中的名称 -> 简化名称）
                wt_name_map = {
                    "装移拆": "装移拆", "投诉": "投诉", "LAN口": "LAN口",
                    "LAN口（到个人）": "LAN口",
                    "巡检": "巡检", "一户一案": "一户一案", "质差弱光": "质差弱光",
                }
                # 当日工作类型映射
                today_name_map = {
                    "装移拆": "装移拆", "投诉归档": "投诉", "投诉": "投诉",
                    "LAN口": "LAN口",
                    "巡检（当日）": "巡检", "巡检": "巡检",
                    "一户一案": "一户一案", "质差弱光": "质差弱光",
                }
                excluded_work_types = {"小计", "请假"}

                for idx, cell in enumerate(row2):
                    if cell is None:
                        continue
                    cell_str = str(cell).strip()
                    # 跳过排除的工作类型列
                    if cell_str in excluded_work_types:
                        continue

                    # 判断属于积压组还是当日组
                    if backlog_group_start is not None and idx >= backlog_group_start:
                        if today_group_start is not None and idx >= today_group_start:
                            # 在当日组
                            wt_simple = today_name_map.get(cell_str, cell_str)
                            for orig, simple in today_name_map.items():
                                if orig in cell_str:
                                    wt_simple = simple
                                    break
                            if wt_simple not in excluded_work_types and wt_simple not in wt_col_map:
                                wt_col_map[wt_simple] = {"backlog": None, "today": None}
                            if wt_simple not in excluded_work_types:
                                wt_col_map[wt_simple]["today"] = idx
                        else:
                            # 在积压组（当日组还没开始）
                            for orig, simple in wt_name_map.items():
                                if orig in cell_str:
                                    if simple not in excluded_work_types and simple not in wt_col_map:
                                        wt_col_map[simple] = {"backlog": None, "today": None}
                                    if simple not in excluded_work_types:
                                        wt_col_map[simple]["backlog"] = idx
                                    break

                # 流式遍历数据行（从Row3开始）
                for row in rows_data2[3:]:
                    if not row:
                        continue

                    # 提取区域，过滤横山
                    area = ""
                    if area_col is not None and area_col < len(row) and row[area_col]:
                        area = str(row[area_col]).strip()

                    # 只保留横山人员
                    if "横山" not in area:
                        continue

                    # 提取姓名
                    name_idx = name_col if name_col is not None else 1
                    if name_idx >= len(row) or not row[name_idx]:
                        continue
                    worker_name = str(row[name_idx]).strip()
                    if not worker_name or worker_name in ("nan", "#N/A"):
                        continue

                    # 提取网格
                    worker_grid = ""
                    if grid_col is not None and grid_col < len(row) and row[grid_col]:
                        worker_grid = str(row[grid_col]).strip()

                    # 提取各工作类型的积压和当日数据
                    workload: dict[str, dict[str, int]] = {}
                    total_backlog = 0
                    total_today = 0

                    for wt, cols in wt_col_map.items():
                        backlog_idx = cols.get("backlog")
                        today_idx = cols.get("today")

                        backlog_val = 0
                        today_val = 0

                        if backlog_idx is not None and backlog_idx < len(row) and row[backlog_idx] is not None:
                            try:
                                v = str(row[backlog_idx]).strip()
                                if v and v not in ("#N/A", "nan"):
                                    backlog_val = int(float(v))
                            except (ValueError, TypeError):
                                pass

                        if today_idx is not None and today_idx < len(row) and row[today_idx] is not None:
                            try:
                                v = str(row[today_idx]).strip()
                                if v and v not in ("#N/A", "nan"):
                                    today_val = int(float(v))
                            except (ValueError, TypeError):
                                pass

                        workload[wt] = {"backlog": backlog_val, "today": today_val}
                        total_backlog += backlog_val
                        total_today += today_val

                    workers.append({
                        "worker_name": worker_name,
                        "area": area,
                        "grid": worker_grid,
                        "workload": workload,
                        "total_backlog": total_backlog,
                        "total_today": total_today,
                    })

                logger.info(f"全市装维工作量统计横山到个人: {filename} -> {len(workers)} 人")
            else:
                logger.warning(f"全市装维工作量统计: {filename} '到个人'sheet数据行不足")
        else:
            logger.warning(f"全市装维工作量统计: {filename} 缺少'到个人'sheet")

        wb.close()
        return {
            "summary": summary,
            "workers": workers,
            "filename": filename,
            "report_date": report_date,
        }

    except Exception as e:
        logger.error(f"解析全市装维工作量统计失败 {filename}: {e}", exc_info=True)
        return {"summary": None, "workers": [], "filename": filename, "report_date": report_date}


async def reparse_city_workload(db: AsyncSession, directory: Optional[str] = None) -> dict:
    """
    重新解析全市装维工作量统计文件，提取横山汇总指标和人员明细，更新数据库。
    删除旧数据并写入新数据。
    """
    if directory is None:
        directory = settings.watch_dir

    # 在线程池中解析
    result = await asyncio.to_thread(_parse_city_workload_files, directory)

    # 导入模型
    from app.core.models import CityWorkloadSummary, CityWorkloadWorker
    from sqlalchemy import delete as _delete

    # 删除旧数据
    await db.execute(_delete(CityWorkloadSummary))
    await db.execute(_delete(CityWorkloadWorker))

    # ── 写入汇总表 ──
    summary_count = 0
    if result["summary"]:
        s = result["summary"]
        cws = CityWorkloadSummary(
            report_date=result["report_date"] or "",
            district=s.get("district", "横山"),
            total_staff=s.get("total_staff", ""),
            working_staff=s.get("working_staff", ""),
            leave_staff=s.get("leave_staff", ""),
            no_work_ratio=s.get("no_work_ratio", ""),
        )
        db.add(cws)
        summary_count = 1

    # ── 获取或创建报表类型 ──
    stmt = select(ReportType).where(ReportType.name == "全市装维工作量统计")
    r = await db.execute(stmt)
    report_type = r.scalar_one_or_none()
    if not report_type:
        report_type = ReportType(name="全市装维工作量统计", category="装维生产")
        db.add(report_type)
        await db.flush()

    # 删除旧的 report_files/report_records
    old_files_stmt = select(ReportFile.id).where(ReportFile.report_type_id == report_type.id)
    r2 = await db.execute(old_files_stmt)
    old_file_ids = [row[0] for row in r2.all()]
    if old_file_ids:
        await db.execute(_delete(ReportRecord).where(ReportRecord.report_file_id.in_(old_file_ids)))
        await db.execute(_delete(ReportFile).where(ReportFile.report_type_id == report_type.id))

    # 创建 ReportFile
    report_file = ReportFile(
        report_type_id=report_type.id,
        filename=result["filename"] or "",
        file_path=os.path.join(directory, result["filename"] or ""),
        parse_status="parsed",
        record_count=len(result["workers"]),
    )
    db.add(report_file)
    await db.flush()

    # ── 写入人员明细 ──
    worker_count = 0
    for rec in result["workers"]:
        cw = CityWorkloadWorker(
            report_file_id=report_file.id,
            worker_name=rec["worker_name"],
            area=rec["area"],
            grid=rec.get("grid", ""),
            workload=rec["workload"],
            total_backlog=rec["total_backlog"],
            total_today=rec["total_today"],
        )
        db.add(cw)
        worker_count += 1

    # 更新 column_hint
    report_type.column_hint = ["姓名", "区域", "装移拆", "投诉", "LAN口", "巡检", "一户一案", "质差弱光", "小计"]
    report_type.updated_at = datetime.now(timezone.utc)

    await db.commit()

    return {
        "summary_parsed": summary_count,
        "worker_count": worker_count,
        "filename": result["filename"],
        "report_date": result["report_date"],
    }


async def get_city_workload_summary(db: AsyncSession) -> dict:
    """获取全市装维工作量统计横山卡片汇总指标"""
    from app.core.models import CityWorkloadSummary

    stmt = select(CityWorkloadSummary).order_by(CityWorkloadSummary.id.desc()).limit(1)
    r = await db.execute(stmt)
    row = r.scalar_one_or_none()

    if not row:
        return {
            "district": "横山",
            "total_staff": "",
            "working_staff": "",
            "leave_staff": "",
            "no_work_ratio": "",
            "report_date": "",
        }

    return {
        "district": row.district,
        "total_staff": row.total_staff,
        "working_staff": row.working_staff,
        "leave_staff": row.leave_staff,
        "no_work_ratio": row.no_work_ratio,
        "report_date": row.report_date,
    }


async def get_city_workload_workers(db: AsyncSession) -> dict:
    """获取全市装维工作量统计横山装维人员工作量明细列表"""
    from app.core.models import CityWorkloadWorker
    from sqlalchemy import func as _func

    count_stmt = select(_func.count(CityWorkloadWorker.id))
    r = await db.execute(count_stmt)
    total = r.scalar() or 0

    data_stmt = (
        select(CityWorkloadWorker)
        .order_by(CityWorkloadWorker.total_backlog.desc())
    )
    r2 = await db.execute(data_stmt)
    rows = r2.scalars().all()

    workers = []
    for row in rows:
        workers.append({
            "id": row.id,
            "worker_name": row.worker_name,
            "area": row.area,
            "grid": row.grid or "",
            "workload": row.workload or {},
            "total_backlog": row.total_backlog,
            "total_today": row.total_today,
        })

    return {
        "workers": workers,
        "total": total,
    }
