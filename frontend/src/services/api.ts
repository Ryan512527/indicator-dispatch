const BASE = '/api/v1';

async function fetchJson<T>(url: string, params?: Record<string, string>): Promise<T> {
  const search = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${BASE}${url}${search}`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

import type { ReportType, ReportRecord, WirelessOutageSummary, WirelessOutageTrend, PisiteFaultSummary, AccessLayerFaultSummary, EnterpriseBroadbandSummary, EnterpriseBroadbandBacklogRecord, DailyReportSummary, DailyReportBacklogRecord, CityWorkloadSummary, CityWorkloadWorker, FiveCategoryWithdrawalSummary, FiveCategoryWithdrawalDetailRecord, ComplaintBacklogSummary } from '../types';

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

  // ── 皮站故障横山专用 APIs ──
  getPisiteFaultSummary: () =>
    fetchJson<PisiteFaultSummary>('/reports/pisite-fault/summary'),

  getPisiteFaultDetail: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: Record<string, string>[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/pisite-fault/detail', {
      page: String(page),
      page_size: String(pageSize),
    }),

  reparsePisiteFault: async () => {
    const res = await fetch(`${BASE}/reports/pisite-fault/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 接入层通报横山专用 APIs ──
  getAccessLayerFaultSummary: () =>
    fetchJson<AccessLayerFaultSummary>('/reports/access-layer/summary'),

  getAccessLayerFaultDetail: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: Record<string, string>[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/access-layer/detail', {
      page: String(page),
      page_size: String(pageSize),
    }),

  reparseAccessLayerFault: async () => {
    const res = await fetch(`${BASE}/reports/access-layer/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 企宽装机通报横山专用 APIs ──
  getEnterpriseBroadbandSummary: () =>
    fetchJson<EnterpriseBroadbandSummary>('/reports/enterprise-broadband/summary'),

  getEnterpriseBroadbandBacklog: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: EnterpriseBroadbandBacklogRecord[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/enterprise-broadband/backlog', {
      page: String(page),
      page_size: String(pageSize),
    }),

  reparseEnterpriseBroadband: async () => {
    const res = await fetch(`${BASE}/reports/enterprise-broadband/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 日报横山专用 APIs ──
  getDailyReportSummary: () =>
    fetchJson<DailyReportSummary>('/reports/daily-report/summary'),

  getDailyReportBacklog: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: DailyReportBacklogRecord[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/daily-report/backlog', {
      page: String(page),
      page_size: String(pageSize),
    }),

  reparseDailyReport: async () => {
    const res = await fetch(`${BASE}/reports/daily-report/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 全市装维工作量统计横山专用 APIs ──
  getCityWorkloadSummary: () =>
    fetchJson<CityWorkloadSummary>('/reports/city-workload/summary'),

  getCityWorkloadWorkers: () =>
    fetchJson<{
      workers: CityWorkloadWorker[];
      total: number;
    }>('/reports/city-workload/workers'),

  reparseCityWorkload: async () => {
    const res = await fetch(`${BASE}/reports/city-workload/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 五类工单退撤单情况横山专用 APIs ──
  getFiveCategoryWithdrawalSummary: () =>
    fetchJson<FiveCategoryWithdrawalSummary>('/reports/five-category-withdrawal/summary'),

  getFiveCategoryWithdrawalDetails: (page = 1, pageSize = 50) =>
    fetchJson<{
      records: FiveCategoryWithdrawalDetailRecord[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/five-category-withdrawal/detail', {
      page: String(page),
      page_size: String(pageSize),
    }),

  reparseFiveCategoryWithdrawal: async () => {
    const res = await fetch(`${BASE}/reports/five-category-withdrawal/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 宽带在途投诉清单横山专用 APIs ──
  getComplaintBacklogSummary: () =>
    fetchJson<ComplaintBacklogSummary>('/reports/complaint-backlog/summary'),

  reparseComplaintBacklog: async () => {
    const res = await fetch(`${BASE}/reports/complaint-backlog/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },
};
