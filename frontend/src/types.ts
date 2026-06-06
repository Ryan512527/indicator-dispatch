export interface Indicator {
  id: string;
  name: string;
  code: string;
  category: string;
  unit: string;
  tags: string[];
  created_at: string;
}

export interface IndicatorEvent {
  id: string;
  time: string;
  indicator_id: string;
  indicator_name?: string;
  value: number;
  source: string;
  dimensions: Record<string, string>;
}

export interface AggregateResult {
  bucket: string;
  value: number;
}

export interface ChatResponse {
  intent: string;
  data: {
    type: string;
    content?: string;
    columns?: string[];
    rows?: Record<string, string>[];
    categories?: string[];
    values?: number[];
  };
}

export interface ReportType {
  id: number;
  name: string;
  category: string;
  column_hint: string[];
  file_count: number;
  record_count: number;
  latest_time: string | null;
  latest_filename: string | null;
  latest_preview: Record<string, string>[];
  created_at: string;
}

export interface ReportRecord {
  [key: string]: string;
  _source_file: string;
  _created_at: string;
}

export type Page =
  | { name: "dashboard" }
  | { name: "ai-chat" }
  | { name: "detail"; params: { start?: string; end?: string; title?: string; category?: string } }
  | { name: "report-detail"; params: { id: number; name: string } }
  | { name: "wireless-outage-detail" }
  | { name: "pisite-fault-detail" }
  | { name: "access-layer-fault-detail" }
  | { name: "enterprise-broadband-backlog" }
  | { name: "daily-report-detail" }
  | { name: "city-workload-detail" }
  | { name: "five-category-withdrawal-detail" }
  | { name: "complaint-10086-detail" };

export interface WirelessOutageSummary {
  total: number;
  alarm_names: string[];
  latest_time: string | null;
  latest_filename: string | null;
}

export interface WirelessOutageTrend {
  hour: string;
  count: number;
}

export interface PisiteFaultSummary {
  total: number;
  vendors: string[];
  latest_time: string | null;
  latest_filename: string | null;
}

export interface AccessLayerFaultSummary {
  total: number;
  business_affected: number;
  business_unaffected: number;
  alarm_code_names: string[];
  latest_time: string | null;
  latest_filename: string | null;
}

export interface EnterpriseBroadbandSummary {
  district: string;
  month_accept: string;
  month_archive: string;
  month_success_rate: string;
  month_reject: string;
  total_backlog: string;
  day_accept: string;
  day_archive: string;
  day_success_rate: string;
  day_reject: string;
  day_backlog: string;
  report_date: string;
}

export interface EnterpriseBroadbandBacklogRecord {
  id: number;
  district: string;
  cover_scene: string;
  account: string;
  address: string;
  worker_name: string;
  accept_time: string;
  to_install_time: string;
  deadline: string;
  install_duration_hours: string;
  user_brand: string;
}

export interface DailyReportSummary {
  report_date: string;
  two_cat: {
    积压总量: string;
    家宽转化率: string;
    FTTR转化率: string;
    总装机转化率: string;
  };
  five_cat: {
    积压总量: string;
    家宽转化率: string;
    智能组网: string;
    平安乡村: string;
    FTTR转化率: string;
    总装机转化率: string;
  };
}

export interface DailyReportBacklogRecord {
  id: number;
  所属区县: string;
  覆盖场景: string;
  宽带账号: string;
  服务: string;
  施工地址: string;
  施工人姓名: string;
  工单状态: string;
  受理时间: string;
  到装维时间: string;
  完成时限: string;
  积压时长h: string;
  ['装机历时(h)']: string;
  时长提醒: string;
  用户品牌: string;
  数据来源: string;
}

export interface CityWorkloadSummary {
  district: string;
  total_staff: string;
  working_staff: string;
  leave_staff: string;
  no_work_ratio: string;
  report_date: string;
}

export interface CityWorkloadWorker {
  id: number;
  worker_name: string;
  area: string;
  grid: string;
  workload: Record<string, { backlog: number; today: number }>;
  total_backlog: number;
  total_today: number;
}

export interface FiveCategoryWithdrawalSummary {
  district: string;
  day_withdrawal_total: string;
  day_reinstall_total: string;
  month_withdrawal_total: string;
  month_reinstall_total: string;
  report_date: string;
}

export interface FiveCategoryWithdrawalDetailRecord {
  id: number;
  district: string;
  account: string;
  global_access: string;
  service_type: string;
  construction_address: string;
  accept_department: string;
  accept_time: string;
  to_install_time: string;
  deadline: string;
  natural_duration: string;
  return_time: string;
  archive_time: string;
  suspected_timeout: string;
  return_note: string;
  specific_reason: string;
}

export interface ComplaintBacklogSummary {
  district: string;
  backlog_10086: string;
  backlog_global: string;
  backlog_2200000: string;
  backlog_86_offline: string;
  total_backlog: string;
  previous_day_backlog: string;
  ratio: string;
  report_date: string;
}

export interface Complaint10086Summary {
  district: string;
  total_not_overdue: string;
  today_need_process: string;
  broadband_business: string;
  total_overdue: string;
  total_backlog: string;
  warn_2h_overdue: string;
  overdue_2_4h: string;
  report_date: string;
}

export interface Complaint10086DetailRecord {
  id: number;
  district: string;
  timeout_deadline: string;
  broadband_account: string;
  global_access: string;
  customer_contact: string;
  customer_urge_count: string;
  community_name: string;
  handler_name: string;
  is_door_service: string;
  complaint_category5: string;
  reply_content: string;
}
