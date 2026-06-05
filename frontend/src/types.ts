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
  | { name: "daily-report-detail" };

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
}
