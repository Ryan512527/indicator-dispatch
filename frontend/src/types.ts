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
  | { name: "pisite-fault-detail" };

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
