const BASE = '/api/v1';

async function fetchJson<T>(url: string, params?: Record<string, string>): Promise<T> {
  const search = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${BASE}${url}${search}`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

import type { ReportType, ReportRecord, WirelessOutageSummary, WirelessOutageTrend } from '../types';

export const api = {
  health: () => fetchJson<{ status: string }>('/health'),

  listIndicators: (params?: { category?: string; search?: string }) =>
    fetchJson<import('../types').Indicator[]>('/indicators', params as Record<string, string>),

  listCategories: () =>
    fetchJson<string[]>('/indicators/categories'),

  queryEvents: (params?: {
    indicator_id?: string;
    category?: string;
    start?: string;
    end?: string;
    limit?: string;
    offset?: string;
  }) => fetchJson<import('../types').IndicatorEvent[]>('/events', params as Record<string, string>),

  aggregateEvents: (params: {
    group_by?: string;
    time_bucket?: string;
    aggregation?: string;
    indicator_id?: string;
    category?: string;
    start?: string;
    end?: string;
  }) => fetchJson<import('../types').AggregateResult[]>('/events/aggregate', params as Record<string, string>),

  aiChat: async (message: string) => {
    const res = await fetch(`${BASE}/ai/chat?message=${encodeURIComponent(message)}`, { method: 'POST' });
    if (!res.ok) throw new Error(`AI chat error: ${res.status}`);
    return res.json() as Promise<import('../types').ChatResponse>;
  },

  // ── Report Data APIs ──
  listReportTypes: () =>
    fetchJson<ReportType[]>('/reports/types'),

  getReportRecords: (typeId: number, page = 1, pageSize = 50) =>
    fetchJson<{
      records: ReportRecord[],
      total: number,
      page: number,
      page_size: number,
    }>(`/reports/types/${typeId}/records`, {
      page: String(page),
      page_size: String(pageSize),
    }),

  scanReports: async (directory?: string) => {
    const res = await fetch(`${BASE}/reports/scan`, {
      method: 'POST',
      ...(directory ? { body: JSON.stringify({ directory }) } : {}),
    });
    if (!res.ok) throw new Error(`Scan failed: ${res.status}`);
    return res.json();
  },

  parseAllReports: async (directory?: string) => {
    const res = await fetch(`${BASE}/reports/parse-all`, { method: 'POST' });
    if (!res.ok) throw new Error(`Parse failed: ${res.status}`);
    return res.json();
  },

  parseReport: async (reportType: string) => {
    const res = await fetch(`${BASE}/reports/parse?report_type=${encodeURIComponent(reportType)}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Parse failed: ${res.status}`);
    return res.json();
  },

  // ── 无线退服横山专用 APIs ──
  getWirelessOutageSummary: () =>
    fetchJson<WirelessOutageSummary>('/reports/wireless-outage/summary'),

  getWirelessOutageDetail: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: Record<string, string>[],
      total: number,
      page: number,
      page_size: number,
    }>('/reports/wireless-outage/detail', {
      page: String(page),
      page_size: String(pageSize),
    }),

  getWirelessOutageTrend: (hours = 48) =>
    fetchJson<WirelessOutageTrend[]>('/reports/wireless-outage/trend', {
      hours: String(hours),
    }),

  reparseWirelessOutage: async () => {
    const res = await fetch(`${BASE}/reports/wireless-outage/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },
};
