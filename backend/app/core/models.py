import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, JSON, Text, ForeignKey, BigInteger, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base


class IndicatorDefinition(Base):
    __tablename__ = "indicator_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, comment="indicator name")
    code = Column(String(128), nullable=False, unique=True, comment="indicator code")
    category = Column(String(128), comment="category")
    unit = Column(String(64), comment="unit")
    tags = Column(JSON, default=list, comment="tags")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IndicatorEvent(Base):
    __tablename__ = "indicator_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    time = Column(DateTime(timezone=True), nullable=False, comment="event time")
    indicator_id = Column(UUID(as_uuid=True), ForeignKey("indicator_definitions.id"), nullable=False)
    value = Column(Float, nullable=False, comment="indicator value")
    source = Column(String(512), comment="source file")
    dimensions = Column(JSON, default=dict, comment="dimensions as key-value pairs")
    extra_data = Column(JSON, default=dict, comment="raw data snapshot for backtracking")

    indicator = relationship("IndicatorDefinition", lazy="joined")


# --- Report data models (for recurring report parsing) ---

class ReportType(Base):
    __tablename__ = "report_types"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(200), nullable=False, unique=True, comment="报表类型名称，如：无线退服清单")
    category = Column(String(100), comment="分类，如：无线、家宽")
    description = Column(Text, comment="描述")
    column_hint = Column(JSON, default=dict, comment="建议展示的字段列表")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ReportFile(Base):
    __tablename__ = "report_files"

    id = Column(BigInteger, primary_key=True)
    report_type_id = Column(BigInteger, ForeignKey("report_types.id"), nullable=False)
    filename = Column(String(500), nullable=False, comment="原始文件名")
    file_path = Column(String(1000), comment="完整文件路径")
    file_time = Column(DateTime(timezone=True), comment="从文件名中提取的时间")
    parse_status = Column(String(50), default="pending", comment="pending / parsed / failed")
    parse_error = Column(Text)
    record_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReportRecord(Base):
    __tablename__ = "report_records"

    id = Column(BigInteger, primary_key=True)
    report_file_id = Column(BigInteger, ForeignKey("report_files.id"), nullable=False, index=True)
    data = Column(JSON, nullable=False, comment="整行数据，JSON key-value")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── 企宽装机通报专用模型 ──

class EnterpriseBroadbandSummary(Base):
    """企宽装机通报 - 横山汇总指标（来自"移动汇报"sheet）"""
    __tablename__ = "enterprise_broadband_summary"

    id = Column(BigInteger, primary_key=True)
    report_date = Column(String(50), comment="通报日期，如 2026-06-04")
    district = Column(String(50), default="横山", comment="区县")
    month_accept = Column(String(50), comment="当月受理量")
    month_archive = Column(String(50), comment="当月归档量")
    month_success_rate = Column(String(50), comment="当月成功率")
    month_reject = Column(String(50), comment="当月退单量")
    total_backlog = Column(String(50), comment="积压总量")
    day_accept = Column(String(50), comment="当日受理量")
    day_archive = Column(String(50), comment="当日归档量")
    day_success_rate = Column(String(50), comment="当日成功率")
    day_reject = Column(String(50), comment="当日退单量")
    day_backlog = Column(String(50), comment="当日积压")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EnterpriseBroadbandBacklog(Base):
    """企宽装机通报 - 横山积压清单（来自"积压"sheet）"""
    __tablename__ = "enterprise_broadband_backlog"

    id = Column(BigInteger, primary_key=True)
    report_file_id = Column(BigInteger, ForeignKey("report_files.id"), nullable=False, index=True)
    district = Column(String(50), comment="所属区县")
    account = Column(String(50), comment="宽带账号")
    address = Column(Text, comment="施工地址")
    worker_name = Column(String(50), comment="施工人姓名")
    accept_time = Column(String(50), comment="受理时间")
    to_install_time = Column(String(50), comment="到装维时间")
    deadline = Column(String(50), comment="完成时限")
    install_duration_hours = Column(String(50), comment="装机历时（h）")
    user_brand = Column(String(50), comment="用户品牌")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── 日报专用模型 ──

class DailyReportSummary(Base):
    """日报 - 横山两类和五类装机成功率（来自"两类"和"五类"sheet）"""
    __tablename__ = "daily_report_summary"

    id = Column(BigInteger, primary_key=True)
    report_date = Column(String(50), comment="通报日期")
    two_cat_backlog_total = Column(String(50), comment="两类-积压总量")
    two_cat_broadband_rate = Column(String(50), comment="两类-家宽转化率")
    two_cat_fttr_rate = Column(String(50), comment="两类-FTTR转化率")
    two_cat_total_rate = Column(String(50), comment="两类-总装机转化率")
    five_cat_backlog_total = Column(String(50), comment="五类-积压总量")
    five_cat_broadband_rate = Column(String(50), comment="五类-家宽转化率")
    five_cat_smart_network = Column(String(50), comment="五类-智能组网")
    five_cat_safe_village = Column(String(50), comment="五类-平安乡村")
    five_cat_fttr_rate = Column(String(50), comment="五类-FTTR转化率")
    five_cat_total_rate = Column(String(50), comment="五类-总装机转化率")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DailyReportBacklog(Base):
    """日报 - 横山装机积压清单（来自"宽带积压"sheet）"""
    __tablename__ = "daily_report_backlog"

    id = Column(BigInteger, primary_key=True)
    report_file_id = Column(BigInteger, ForeignKey("report_files.id"), nullable=False, index=True)
    district = Column(String(50), comment="所属区县")
    coverage_scenario = Column(String(50), comment="覆盖场景")
    account = Column(String(50), comment="宽带账号")
    service = Column(String(200), comment="服务")
    address = Column(Text, comment="施工地址")
    worker_name = Column(String(50), comment="施工人姓名")
    order_status = Column(String(50), comment="工单状态")
    accept_time = Column(String(50), comment="受理时间")
    to_install_time = Column(String(50), comment="到装维时间")
    deadline = Column(String(50), comment="完成时限")
    backlog_hours = Column(String(50), comment="积压时长h")
    install_duration_hours = Column(String(50), comment="装机历时(h)，完成时限 - 到装维时间")
    user_brand = Column(String(50), comment="用户品牌")
    data_source = Column(String(20), comment="数据来源：宽带积压 / FTTR积压")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── 全市装维工作量统计专用模型 ──

class CityWorkloadSummary(Base):
    """全市装维工作量统计 - 横山汇总指标（来自"汇总"sheet）"""
    __tablename__ = "city_workload_summary"

    id = Column(BigInteger, primary_key=True)
    report_date = Column(String(50), comment="通报日期")
    district = Column(String(50), default="横山", comment="区县")
    total_staff = Column(String(50), comment="人员数量")
    working_staff = Column(String(50), comment="有工作量人数（当日）")
    leave_staff = Column(String(50), comment="请假人数")
    no_work_ratio = Column(String(50), comment="无工作量占比（剔除请假）")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CityWorkloadWorker(Base):
    """全市装维工作量统计 - 横山装维人员工作量明细（来自"到个人"sheet）"""
    __tablename__ = "city_workload_workers"

    id = Column(BigInteger, primary_key=True)
    report_file_id = Column(BigInteger, ForeignKey("report_files.id"), nullable=False, index=True)
    worker_name = Column(String(50), comment="装维人员姓名")
    area = Column(String(100), comment="所属区域")
    # 积压和当日工作量按工作类型存储为JSON，结构: {"装移拆": {"backlog": 4, "today": 0}, ...}
    workload = Column(JSON, default=dict, comment="各工作类型积压和当日工作量")
    total_backlog = Column(Integer, default=0, comment="累计积压总量")
    total_today = Column(Integer, default=0, comment="当日工作量总计")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
