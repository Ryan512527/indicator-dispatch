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
  | { name: "enterprise-broadband-backlog" };

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
