export interface Indicator {
  id: string;
  name: string;
  code: string;
  category: string | null;
  unit: string | null;
  tags: string[];
  created_at: string;
}

export interface IndicatorEvent {
  id: string;
  time: string;
  indicator_id: string;
  indicator_name: string | null;
  value: number;
  source: string | null;
  dimensions: Record<string, string>;
}

export interface AggregateResult {
  bucket: string;
  value: number | null;
}

export interface ChatResponse {
  intent: string;
  data: {
    type: 'table' | 'bar' | 'line' | 'text';
    content?: string;
    columns?: string[];
    rows?: Record<string, string | number | null>[];
    title?: string;
    categories?: string[];
    values?: number[];
  };
}
