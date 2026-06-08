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
    title?: string;
  };
  answer?: string;
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
  | { name: "complaint-10086-detail" }
  | { name: "complaint-2200000-detail" }
  | { name: "enterprise-broadband-fault-detail" }
  | { name: "offline-dispatch-detail" }
  | { name: "retry-warning-detail" }
  | { name: "poor-quality-work-order-detail" }
  | { name: "enterprise-broadband-low-light-detail" };

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
  latest_filename: string;
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
  latest_filename: string;
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
  latest_filename: string;
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
  latest_filename: string;
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
  latest_filename: string;
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
  latest_filename: string;
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

export interface Complaint2200000Summary {
  district: string;
  monthly_dispatch: string;
  overdue_backlog: string;
  not_overdue_backlog: string;
  total_in_transit: string;
  previous_month_backlog: string;
  warn_4h_overdue: string;
  escalate_complaint: string;
  report_date: string;
  latest_filename: string;
}

export interface Complaint2200000DetailRecord {
  id: number;
  district: string;
  timeout_deadline: string;
  broadband_account: string;
  is_important_customer: string;
  customer_contact: string;
  construction_address: string;
  handler_name: string;
  category: string;
}

export interface OfflineDispatchSummary {
  district: string;
  monthly_dispatch: string;
  overdue_backlog: string;
  not_overdue_backlog: string;
  total_in_transit: string;
  warn_4h_overdue: string;
  report_date: string;
  latest_filename: string;
}

export interface OfflineDispatchDetailRecord {
  id: number;
  district: string;
  timeout_limit: string;
  broadband_account: string;
  is_vip_customer: string;
  customer_contact: string;
  construction_address: string;
  handler_name: string;
  category: string;
}

export interface OfflineDispatchDetailResponse {
  records: OfflineDispatchDetailRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface RetryWarningSummary {
  district: string;
  retry_2_times: string;
  retry_3_times: string;
  retry_4plus_times: string;
  total_in_transit: string;
  daily_closed: string;
  repair_total: string;
  repair_in_transit: string;
  repair_closed: string;
  report_date: string;
  latest_filename: string;
}

export interface RetryWarningDetailRecord {
  id: number;
  district: string;
  retry_count: string;
  broadband_account: string;
  is_global_user: string;
  customer_contact: string;
  construction_address: string;
  days_elapsed: string;
  handler_name: string;
  complaint_content: string;
}

export interface CustomerRepairDetailRecord {
  id: number;
  district: string;
  repair_count: string;
  account: string;
  call_number: string;
  address: string;
  register_date: string;
}

export interface RetryWarningDetailResponse {
  records: RetryWarningDetailRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface CustomerRepairDetailResponse {
  records: CustomerRepairDetailRecord[];
  total: number;
  page: number;
  page_size: number;
}

// ── 企宽故障率横山专用类型 ──

export interface EnterpriseBroadbandFaultSummary {
  district: string;
  fault_rate: string;
  fault_count: string;
  total_alarm_duration: string;
  unrecoverd_work_orders: string;
  report_date: string;
  latest_filename: string;
}

export interface EnterpriseBroadbandFaultRecord {
  id: number;
  district: string;
  olt_name: string;
  olt_ip: string;
  pon_port: string;
  account: string;
  alarm_total: string;
  alarm_weighted_duration: string;
}

export interface EnterpriseBroadbandFaultResponse {
  records: EnterpriseBroadbandFaultRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface PoorQualityWorkOrderSummary {
  work_order_count: string;
  completed_count: string;
  completion_rate: string;
  community_count: string;
  report_date: string;
  latest_filename: string;
}

export interface PoorQualityWorkOrderRecord {
  id: number;
  district: string;
  work_order_no: string;
  dispatch_time: string;
  deadline: string;
  maintenance_person: string;
  notes: string;
  olt_ip: string;
  olt_port: string;
}

export interface PoorQualityWorkOrderResponse {
  records: PoorQualityWorkOrderRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface EnterpriseBroadbandLowLightSummary {
  district: string;
  total_count: string;
  monthly_completed: string;
  monthly_completion_rate: string;
  county_rank: string;
  report_date: string;
  latest_filename: string;
}

export interface EnterpriseBroadbandLowLightRecord {
  id: number;
  district: string;
  date: string;
  olt_name: string;
  olt_ip: string;
  pon_port: string;
  onu_id: string;
  rx_power_dbm: string;
  community: string;
  account_bandwidth: string;
}

export interface EnterpriseBroadbandLowLightResponse {
  records: EnterpriseBroadbandLowLightRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface BroadbandRedelivery2Summary {
  district: string;
  redelivery2_in_transit: string;
  global_tong_2: string;
  redelivery3: string;
  global_tong_3: string;
  redelivery4_plus: string;
  global_tong_4: string;
  total_in_transit: string;
  redelivery2_processed: string;
  report_date: string;
  time_period: string;
  latest_filename: string;
}

export interface Notification {
  id: number;
  report_type: string;
  filename: string;
  event_time: string;
  is_read: boolean;
}
