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
