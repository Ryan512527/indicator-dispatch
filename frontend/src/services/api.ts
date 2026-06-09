const BASE = '/api/v1';

async function fetchJson<T>(url: string, params?: Record<string, string>): Promise<T> {
  const search = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${BASE}${url}${search}`);
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

import type { ReportType, ReportRecord, WirelessOutageSummary, WirelessOutageTrend, PisiteFaultSummary, AccessLayerFaultSummary, EnterpriseBroadbandSummary, EnterpriseBroadbandBacklogRecord, DailyReportSummary, DailyReportBacklogRecord, CityWorkloadSummary, CityWorkloadWorker, FiveCategoryWithdrawalSummary, FiveCategoryWithdrawalDetailRecord, ComplaintBacklogSummary, Complaint10086Summary, Complaint10086DetailRecord, Complaint2200000Summary, Complaint2200000DetailRecord, OfflineDispatchSummary, OfflineDispatchDetailResponse, RetryWarningSummary, RetryWarningDetailResponse, CustomerRepairDetailResponse, EnterpriseBroadbandFaultSummary, EnterpriseBroadbandFaultRecord, EnterpriseBroadbandFaultResponse, PoorQualityWorkOrderSummary, PoorQualityWorkOrderResponse, EnterpriseBroadbandLowLightSummary, EnterpriseBroadbandLowLightResponse, BroadbandRedelivery2Summary, AIAnalysisResult } from '../types';

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

  aiChat: async (message: string, history?: Array<{role: string; content: string}>) => {
    const res = await fetch(`${BASE}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
    });
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

  getDailyReportBacklog: (page = 1, pageSize = 50, sortBy?: string, order?: string) =>
    fetchJson<{
      records: DailyReportBacklogRecord[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/daily-report/backlog', {
      page: String(page),
      page_size: String(pageSize),
      ...(sortBy ? { sort_by: sortBy, order: order || 'asc' } : {}),
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

  // ── 10086投诉积压(督办)横山专用 APIs ──
  getComplaint10086Summary: () =>
    fetchJson<Complaint10086Summary>('/reports/complaint-10086/summary'),

  getComplaint10086Details: (page = 1, pageSize = 50, sortBy?: string, order?: string) =>
    fetchJson<{
      records: Complaint10086DetailRecord[];
      total: number;
      page: number;
      page_size: number;
    }>('/reports/complaint-10086/detail', {
      page: String(page),
      page_size: String(pageSize),
      ...(sortBy ? { sort_by: sortBy, order: order || 'asc' } : {}),
    }),

  reparseComplaint10086: async () => {
    const res = await fetch(`${BASE}/reports/complaint-10086/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 2200000及时率通报 ──
  getComplaint2200000Summary: async () => {
    return fetchJson<Complaint2200000Summary>('/reports/complaint-2200000/summary');
  },
  getComplaint2200000Details: async (page = 1, pageSize = 50, sortBy?: string, order?: string) => {
    let url = `/reports/complaint-2200000/detail?page=${page}&page_size=${pageSize}`;
    if (sortBy) url += `&sort_by=${encodeURIComponent(sortBy)}`;
    if (order) url += `&order=${encodeURIComponent(order)}`;
    return fetchJson<{ records: Complaint2200000DetailRecord[]; total: number; page: number; page_size: number }>(url);
  },
  reparseComplaint2200000: async () => {
    const res = await fetch(`${BASE}/reports/complaint-2200000/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── AI 分析 (贾维斯) ──
  getAIAnalysis: async (cardType: string, forceRefresh = false) => {
    const res = await fetch(`${BASE}/ai/analysis/${cardType}?force_refresh=${forceRefresh}`);
    if (!res.ok) throw new Error(`AI analysis failed: ${res.status}`);
    return res.json();
  },
  refreshAIAnalysis: async (cardType: string) => {
    const res = await fetch(`${BASE}/ai/analysis/${cardType}/refresh`, { method: 'POST' });
    if (!res.ok) throw new Error(`AI refresh failed: ${res.status}`);
    return res.json();
  },

  // ── 线下派单处理情况 ──
  getOfflineDispatchSummary: async () => {
    return fetchJson<OfflineDispatchSummary>('/reports/offline-dispatch/summary');
  },
  reparseOfflineDispatch: async () => {
    const res = await fetch(`${BASE}/reports/offline-dispatch/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },
  getOfflineDispatchDetails: async (page = 1, pageSize = 50, category?: string, sortBy?: string, order?: string) => {
    const qs = new URLSearchParams();
    if (category) qs.set('category', category);
    qs.set('page', String(page));
    qs.set('page_size', String(pageSize));
    if (sortBy) { qs.set('sort_by', sortBy); qs.set('order', order || 'asc'); }
    return fetchJson<OfflineDispatchDetailResponse>(`/reports/offline-dispatch/details?${qs.toString()}`);
  },

  // ── 重投预警工单梳理 ──
  getRetryWarningSummary: async () => {
    return fetchJson<RetryWarningSummary>('/reports/retry-warning/summary');
  },
  reparseRetryWarning: async () => {
    const res = await fetch(`${BASE}/reports/retry-warning/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },
  getRetryWarningDetails: async (params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    return fetchJson<RetryWarningDetailResponse>(`/reports/retry-warning/retry-details?${qs.toString()}`);
  },
  getCustomerRepairDetails: async (params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    return fetchJson<CustomerRepairDetailResponse>(`/reports/retry-warning/repair-details?${qs.toString()}`);
  },

  // ── 企宽故障率横山专用 APIs ──
  getEnterpriseBroadbandFaultSummary: () =>
    fetchJson<EnterpriseBroadbandFaultSummary>('/reports/enterprise-broadband-fault/summary'),

  getEnterpriseBroadbandFaultDetails: (params?: {
    page?: number;
    page_size?: number;
    sort_field?: string;
    sort_order?: string;
    district?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    if (params?.sort_field) qs.set('sort_field', params.sort_field);
    if (params?.sort_order) qs.set('sort_order', params.sort_order);
    if (params?.district) qs.set('district', params.district);
    return fetchJson<EnterpriseBroadbandFaultResponse>(`/reports/enterprise-broadband-fault/details?${qs.toString()}`);
  },

  reparseEnterpriseBroadbandFault: async () => {
    const res = await fetch(`${BASE}/reports/enterprise-broadband-fault/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 质差小区弱光工单 API ──

  getPoorQualityWorkOrderSummary: async () => {
    return fetchJson<PoorQualityWorkOrderSummary>('/reports/poor-quality-work-order/summary');
  },

  getPoorQualityWorkOrderDetails: async (params?: {
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    return fetchJson<PoorQualityWorkOrderResponse>(`/reports/poor-quality-work-order/details?${qs.toString()}`);
  },

  reparsePoorQualityWorkOrder: async () => {
    const res = await fetch(`${BASE}/reports/poor-quality-work-order/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 企宽弱光通报 API ──

  getEnterpriseBroadbandLowLightSummary: async () => {
    return fetchJson<EnterpriseBroadbandLowLightSummary>('/reports/enterprise-broadband-low-light/summary');
  },

  getEnterpriseBroadbandLowLightDetails: async (params?: {
    page?: number;
    page_size?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    return fetchJson<EnterpriseBroadbandLowLightResponse>(`/reports/enterprise-broadband-low-light/details?${qs.toString()}`);
  },

  reparseEnterpriseBroadbandLowLight: async () => {
    const res = await fetch(`${BASE}/reports/enterprise-broadband-low-light/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

  // ── 家宽重投2次 API ──

  getBroadbandRedelivery2Summary: async () => {
    return fetchJson<BroadbandRedelivery2Summary>('/reports/broadband-redelivery2/summary');
  },

  reparseBroadbandRedelivery2: async () => {
    const res = await fetch(`${BASE}/reports/broadband-redelivery2/reparse`, { method: 'POST' });
    if (!res.ok) throw new Error(`Reparse failed: ${res.status}`);
    return res.json();
  },

// ── Notification APIs ──
  getNotifications: (limit = 10) =>
    fetchJson<import('../types').Notification[]>(`/notifications`, { limit: String(limit) }),

  markNotificationRead: async (id: number) => {
    const res = await fetch(`${BASE}/notifications/${id}/read`, { method: 'POST' });
    if (!res.ok) throw new Error(`Mark read failed: ${res.status}`);
    return res.json();
  },

  markAllNotificationsRead: async () => {
    const res = await fetch(`${BASE}/notifications/read-all`, { method: 'POST' });
    if (!res.ok) throw new Error(`Mark all read failed: ${res.status}`);
    return res.json();
  },
};
