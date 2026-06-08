import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { Page, ReportType, WirelessOutageSummary, PisiteFaultSummary, AccessLayerFaultSummary, EnterpriseBroadbandSummary, DailyReportSummary, CityWorkloadSummary, FiveCategoryWithdrawalSummary, ComplaintBacklogSummary, Complaint10086Summary, Complaint10086DetailRecord, Complaint2200000Summary, Complaint2200000DetailRecord, OfflineDispatchSummary, OfflineDispatchDetailRecord, RetryWarningSummary, EnterpriseBroadbandFaultSummary, PoorQualityWorkOrderSummary, EnterpriseBroadbandLowLightSummary, BroadbandRedelivery2Summary } from '../types'

function fmt(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ── 分类定义 ──
interface CategoryConfig {
  name: string
  color: string
  keywords: string[]
}

const CATEGORIES: CategoryConfig[] = [
  {
    name: '第一类：故障类',
    color: '#ef4444',
    keywords: ['无线退服清单', '皮站故障清单', '接入层通报', '榆林未恢复故障统计'],
  },
  {
    name: '第二类：装维生产类',
    color: '#3b82f6',
    keywords: ['企宽装机通报', '日报', '五类工单退撤单情况', '全市装维工作量统计', '家宽+FTTR遗留工单安装进度通报', 'H5当日闭环测评清单', '企宽开通及时率通报', '成功率攻坚通报', '触点用后即评'],
  },
  {
    name: '第三类：投诉类',
    color: '#f59e0b',
    keywords: ['宽带在途投诉清单', '线下派单处理情况', '10086投诉积压(督办)', '重投预警工单梳理', '2200000及时率通报', '家宽重投2次清单明细', '投诉积压大于3单人员通报', '投诉三类工单在途情况'],
  },
  {
    name: '第四类：质差整治类',
    color: '#10b981',
    keywords: ['质差客户整治完成率通报', '质差小区弱光工单处理完成率', '企宽弱光通报', '企宽故障率', '一二级分支真实处理通报', '一户一案'],
  },
]

function classifyReport(rt: ReportType): CategoryConfig | null {
  for (const cat of CATEGORIES) {
    for (const kw of cat.keywords) {
      if (rt.name.includes(kw)) {
        return cat
      }
    }
  }
  return null
}

// 提取报表预览中有意义的列（排除 col_ 开头的占位列和空值过多的列）
function getMeaningfulColumns(records: Record<string, string>[], maxCols = 4): string[] {
  if (!records || records.length === 0) return []
  const allKeys = Array.from(new Set(records.flatMap(r => Object.keys(r))))
  const candidates = allKeys.filter(k =>
    !k.startsWith('_') && !k.startsWith('col_') && k !== 'row_num'
  )
  if (candidates.length > 0) return candidates.slice(0, maxCols)
  return allKeys.filter(k => !k.startsWith('_')).slice(0, maxCols)
}

// ── 单张报表卡片 ──
function ReportCard({ rt, color, onNavigate }: { rt: ReportType; color: string; onNavigate: (p: Page) => void }) {
  const preview = rt.latest_preview || []
  const columns = getMeaningfulColumns(preview, 4)
  const hasPreview = preview.length > 0 && columns.length > 0

  return (
    <div
      onClick={() => onNavigate({ name: 'report-detail', params: { id: rt.id, name: rt.name } })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>{rt.name}</div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {rt.file_count} 个文件
        </span>
      </div>

      {/* 数据预览区 */}
      {hasPreview ? (
        <div style={{ flex: 1, overflow: 'hidden', marginBottom: 10 }}>
          <div style={{
            overflowX: 'auto',
            borderRadius: 6,
            border: '1px solid #f0f0f0',
            fontSize: 11,
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 200 }}>
              <thead>
                <tr style={{ background: '#fafafa' }}>
                  {columns.map(col => (
                    <th key={col} style={{
                      padding: '4px 8px',
                      textAlign: 'left',
                      color: '#666',
                      fontWeight: 600,
                      borderBottom: '1px solid #eee',
                      whiteSpace: 'nowrap',
                    }}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.slice(0, 4).map((row, i) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                    {columns.map(col => (
                      <td key={col} style={{
                        padding: '4px 8px',
                        color: '#333',
                        borderBottom: '1px solid #f5f5f5',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: 120,
                      }} title={row[col] || ''}>
                        {row[col] || '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.length > 4 && (
            <div style={{ fontSize: 11, color: '#aaa', textAlign: 'right', marginTop: 4 }}>
              还有 {preview.length - 4} 条记录…
            </div>
          )}
        </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#ccc',
          fontSize: 12,
          minHeight: 60,
          marginBottom: 10,
        }}>
          暂无预览数据
        </div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={rt.latest_filename || ''}>
            📄 {rt.latest_filename || '—'}
          </span>
          <span>
            {rt.latest_time ? fmt(rt.latest_time) : '—'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── 无线退服专用卡片 ──
function WirelessOutageCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<WirelessOutageSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getWirelessOutageSummary()
      .then(data => setSummary(data as WirelessOutageSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 160,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>无线退服清单</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const total = summary?.total ?? 0
  const alarmNames = summary?.alarm_names ?? []
  const latestTime = summary?.latest_time
  const latestFilename = summary?.latest_filename

  return (
    <div
      onClick={() => onNavigate({ name: 'wireless-outage-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>无线退服清单</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fef2f2',
            color: '#ef4444',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {latestTime ? fmt(latestTime) : '—'}
        </span>
      </div>

      {/* 核心数字 */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: total > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.1 }}>
          {total}
        </div>
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          当前退服基站数
        </div>
      </div>

      {/* 告警名称列表 */}
      {alarmNames.length > 0 ? (
        <div style={{
          flex: 1,
          background: '#fafafa',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
        }}>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 6 }}>告警类型</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 6px' }}>
            {alarmNames.slice(0, 6).map((name, i) => (
              <span key={i} style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: 4,
                background: '#fff',
                border: '1px solid #fee2e2',
                color: '#dc2626',
                fontSize: 11,
                whiteSpace: 'nowrap',
              }}>
                {name}
              </span>
            ))}
            {alarmNames.length > 6 && (
              <span style={{ fontSize: 11, color: '#999', alignSelf: 'center' }}>
                +{alarmNames.length - 6} 种
              </span>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          flex: 1,
          background: '#f0fdf4',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <span style={{ fontSize: 12, color: '#22c55e' }}>✅ 当前无退服告警</span>
        </div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename || ''}>
            📄 {latestFilename || '—'}
          </span>
          <span>点击查看详情 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 接入层通报专用卡片 ──
function AccessLayerFaultCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<AccessLayerFaultSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAccessLayerFaultSummary()
      .then(data => setSummary(data as AccessLayerFaultSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 160,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>接入层通报</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const total = summary?.total ?? 0
  const businessAffected = summary?.business_affected ?? 0
  const businessUnaffected = summary?.business_unaffected ?? 0
  const alarmCodeNames = summary?.alarm_code_names ?? []
  const latestTime = summary?.latest_time
  const latestFilename = summary?.latest_filename

  return (
    <div
      onClick={() => onNavigate({ name: 'access-layer-fault-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>接入层通报</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fef2f2',
            color: '#ef4444',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {latestTime ? fmt(latestTime) : '—'}
        </span>
      </div>

      {/* 核心数字：总故障数 */}
      <div style={{ textAlign: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: total > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.1 }}>
          {total}
        </div>
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          当前接入层故障数
        </div>
      </div>

      {/* 影响/不影响业务 双指标 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <div style={{
          flex: 1,
          background: '#fef2f2',
          borderRadius: 8,
          padding: '8px 10px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444', lineHeight: 1.2 }}>
            {businessAffected}
          </div>
          <div style={{ fontSize: 10, color: '#dc2626' }}>
            影响业务
          </div>
        </div>
        <div style={{
          flex: 1,
          background: '#f0fdf4',
          borderRadius: 8,
          padding: '8px 10px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#22c55e', lineHeight: 1.2 }}>
            {businessUnaffected}
          </div>
          <div style={{ fontSize: 10, color: '#16a34a' }}>
            不影响业务
          </div>
        </div>
      </div>

      {/* 告警码名称列表 */}
      {alarmCodeNames.length > 0 ? (
        <div style={{
          flex: 1,
          background: '#fafafa',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
        }}>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 6 }}>告警码类型</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 6px' }}>
            {alarmCodeNames.slice(0, 6).map((name, i) => (
              <span key={i} style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: 4,
                background: '#fff',
                border: '1px solid #fee2e2',
                color: '#dc2626',
                fontSize: 11,
                whiteSpace: 'nowrap',
              }}>
                {name}
              </span>
            ))}
            {alarmCodeNames.length > 6 && (
              <span style={{ fontSize: 11, color: '#999', alignSelf: 'center' }}>
                +{alarmCodeNames.length - 6} 种
              </span>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          flex: 1,
          background: '#f0fdf4',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <span style={{ fontSize: 12, color: '#22c55e' }}>✅ 当前无接入层故障</span>
        </div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename || ''}>
            📄 {latestFilename || '—'}
          </span>
          <span>点击查看详情 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 皮站故障专用卡片 ──
function PisiteFaultCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<PisiteFaultSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getPisiteFaultSummary()
      .then(data => setSummary(data as PisiteFaultSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 160,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>皮站故障清单</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const total = summary?.total ?? 0
  const vendors = summary?.vendors ?? []
  const latestFilename = summary?.latest_filename

  return (
    <div
      onClick={() => onNavigate({ name: 'pisite-fault-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>皮站故障清单</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fef2f2',
            color: '#ef4444',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {latestFilename ? latestFilename.substring(0, 20) + '...' : '—'}
        </span>
      </div>

      {/* 核心数字 */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: total > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.1 }}>
          {total}
        </div>
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          当前皮站故障数
        </div>
      </div>

      {/* 设备厂商列表 */}
      {vendors.length > 0 ? (
        <div style={{
          flex: 1,
          background: '#fafafa',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
        }}>
          <div style={{ fontSize: 11, color: '#999', marginBottom: 6 }}>设备厂商</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 6px' }}>
            {vendors.slice(0, 6).map((name, i) => (
              <span key={i} style={{
                display: 'inline-block',
                padding: '2px 8px',
                borderRadius: 4,
                background: '#fff',
                border: '1px solid #e5e7eb',
                color: '#374151',
                fontSize: 11,
                whiteSpace: 'nowrap',
              }}>
                {name}
              </span>
            ))}
            {vendors.length > 6 && (
              <span style={{ fontSize: 11, color: '#999', alignSelf: 'center' }}>
                +{vendors.length - 6} 个
              </span>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          flex: 1,
          background: '#f0fdf4',
          borderRadius: 8,
          padding: '10px 12px',
          marginBottom: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <span style={{ fontSize: 12, color: '#22c55e' }}>✅ 当前无皮站故障</span>
        </div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename || ''}>
            📄 {latestFilename || '—'}
          </span>
          <span>点击查看详情 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 企宽装机通报专用卡片 ──
function EnterpriseBroadbandCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<EnterpriseBroadbandSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getEnterpriseBroadbandSummary()
      .then(data => setSummary(data as EnterpriseBroadbandSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 280,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>企宽装机通报</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const fmtPercent = (v: string) => {
    const n = parseFloat(v)
    if (isNaN(n)) return v
    return (n * 100).toFixed(1) + '%'
  }

  return (
    <div
      onClick={() => onNavigate({ name: 'enterprise-broadband-backlog' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>企宽装机通报</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#eff6ff',
            color: '#3b82f6',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 当月指标 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 8, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📊 当月指标
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6 }}>
          {[
            { label: '受理量', value: summary?.month_accept || '—', key: 'month_accept' },
            { label: '归档量', value: summary?.month_archive || '—', key: 'month_archive' },
            { label: '成功率', value: summary?.month_success_rate ? fmtPercent(summary.month_success_rate) : '—', key: 'month_success_rate' },
            { label: '退单量', value: summary?.month_reject || '—', key: 'month_reject' },
            { label: '积压总量', value: summary?.total_backlog || '—', key: 'total_backlog' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#f8fafc',
              borderRadius: 6,
              padding: '6px 4px',
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#1e40af', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 当日指标 */}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 8, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📋 当日指标
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6 }}>
          {[
            { label: '受理量', value: summary?.day_accept || '—', key: 'day_accept' },
            { label: '归档量', value: summary?.day_archive || '—', key: 'day_archive' },
            { label: '成功率', value: summary?.day_success_rate ? fmtPercent(summary.day_success_rate) : '—', key: 'day_success_rate' },
            { label: '退单量', value: summary?.day_reject || '—', key: 'day_reject' },
            { label: '当日积压', value: summary?.day_backlog || '—', key: 'day_backlog' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#f0fdf4',
              borderRadius: 6,
              padding: '6px 4px',
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#166534', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看积压清单 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 日报专用卡片 ──
function DailyReportCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<DailyReportSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getDailyReportSummary()
      .then(data => setSummary(data as DailyReportSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 280,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>日报</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const fmtPercent = (v: string) => {
    const n = parseFloat(v)
    if (isNaN(n)) return v || '—'
    return (n * 100).toFixed(1) + '%'
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''

  return (
    <div
      onClick={() => onNavigate({ name: 'daily-report-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>日报</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#eff6ff',
            color: '#3b82f6',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 五类装机成功率 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 8, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📊 五类装机成功率
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
          {[
            { label: '积压总量', value: summary?.five_cat?.积压总量 || '—', key: 'five_backlog' },
            { label: '家宽转化率', value: summary?.five_cat?.家宽转化率 ? fmtPercent(summary.five_cat.家宽转化率) : '—', key: 'five_broadband' },
            { label: '智能组网', value: summary?.five_cat?.智能组网 ? fmtPercent(summary.five_cat.智能组网) : '—', key: 'five_smart' },
            { label: '平安乡村', value: summary?.five_cat?.平安乡村 ? fmtPercent(summary.five_cat.平安乡村) : '—', key: 'five_village' },
            { label: 'FTTR转化率', value: summary?.five_cat?.FTTR转化率 ? fmtPercent(summary.five_cat.FTTR转化率) : '—', key: 'five_fttr' },
            { label: '总装机转化率', value: summary?.five_cat?.总装机转化率 ? fmtPercent(summary.five_cat.总装机转化率) : '—', key: 'five_total' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#f0fdf4',
              borderRadius: 6,
              padding: '6px 4px',
            }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#166534', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 两类装机成功率 */}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 8, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📋 两类装机成功率
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
          {[
            { label: '积压总量', value: summary?.two_cat?.积压总量 || '—', key: 'two_backlog' },
            { label: '家宽转化率', value: summary?.two_cat?.家宽转化率 ? fmtPercent(summary.two_cat.家宽转化率) : '—', key: 'two_broadband' },
            { label: 'FTTR转化率', value: summary?.two_cat?.FTTR转化率 ? fmtPercent(summary.two_cat.FTTR转化率) : '—', key: 'two_fttr' },
            { label: '总装机转化率', value: summary?.two_cat?.总装机转化率 ? fmtPercent(summary.two_cat.总装机转化率) : '—', key: 'two_total' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#f8fafc',
              borderRadius: 6,
              padding: '6px 4px',
            }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#1e40af', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `日报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看积压清单 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 全市装维工作量统计专用卡片 ──
function CityWorkloadCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<CityWorkloadSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getCityWorkloadSummary()
      .then(data => setSummary(data as CityWorkloadSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>全市装维工作量统计</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''

  return (
    <div
      onClick={() => onNavigate({ name: 'city-workload-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>全市装维工作量统计</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#eff6ff',
            color: '#3b82f6',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 4个核心指标 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 10 }}>
        {[
          { label: '人员数量', value: summary?.total_staff || '—', key: 'total_staff', bg: '#f8fafc', color: '#1e40af' },
          { label: '有工作量人数', value: summary?.working_staff || '—', key: 'working_staff', bg: '#f0fdf4', color: '#166534' },
          { label: '请假人数', value: summary?.leave_staff || '—', key: 'leave_staff', bg: '#fef2f2', color: '#dc2626' },
          { label: '无工作量占比', value: summary?.no_work_ratio || '—', key: 'no_work_ratio', bg: '#fff7ed', color: '#c2410c' },
        ].map(item => (
          <div key={item.key} style={{
            textAlign: 'center',
            background: item.bg,
            borderRadius: 8,
            padding: '10px 6px',
          }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: item.color, lineHeight: 1.2 }}>
              {item.value}
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 4 }}>
              {item.label}
            </div>
          </div>
        ))}
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `统计 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看人员明细 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 五类工单退撤单情况专用卡片 ──
function FiveCategoryWithdrawalCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<FiveCategoryWithdrawalSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getFiveCategoryWithdrawalSummary()
      .then(data => setSummary(data as FiveCategoryWithdrawalSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 250,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>五类工单退撤单情况</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''

  return (
    <div
      onClick={() => onNavigate({ name: 'five-category-withdrawal-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>五类工单退撤单情况</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#eff6ff',
            color: '#3b82f6',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 日粒度指标 */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 6, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📅 日粒度（宽带含FTTR）
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          {[
            { label: '退撤总量', value: summary?.day_withdrawal_total || '—', key: 'day_withdrawal' },
            { label: '退撤单重装量', value: summary?.day_reinstall_total || '—', key: 'day_reinstall' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#f0fdf4',
              borderRadius: 6,
              padding: '8px 4px',
            }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#166534', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 月粒度指标 */}
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 6, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          📊 月粒度（宽带含FTTR）
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          {[
            { label: '退撤总量', value: summary?.month_withdrawal_total || '—', key: 'month_withdrawal' },
            { label: '退撤单重装量', value: summary?.month_reinstall_total || '—', key: 'month_reinstall' },
          ].map(item => (
            <div key={item.key} style={{
              textAlign: 'center',
              background: '#eff6ff',
              borderRadius: 6,
              padding: '8px 4px',
            }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#1e40af', lineHeight: 1.2 }}>
                {item.value}
              </div>
              <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看退撤单明细 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 宽带在途投诉清单专用卡片 ──
function ComplaintBacklogCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<ComplaintBacklogSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getComplaintBacklogSummary()
      .then(data => setSummary(data as ComplaintBacklogSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>宽带在途投诉清单</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const totalBacklog = summary?.total_backlog || '—'
  const backlog10086 = summary?.backlog_10086 || '—'
  const backlogGlobal = summary?.backlog_global || '—'
  const backlog2200000 = summary?.backlog_2200000 || '—'
  const backlog86Offline = summary?.backlog_86_offline || '—'
  const previousDayBacklog = summary?.previous_day_backlog || '—'
  const ratio = summary?.ratio || '—'

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>宽带在途投诉清单</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fef2f2',
            color: '#ef4444',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 合计 */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: totalBacklog !== '—' && parseInt(totalBacklog) > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.1 }}>
          {totalBacklog}
        </div>
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          当前在途投诉合计
        </div>
      </div>

      {/* 各渠道积压量 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginBottom: 10 }}>
        {[
          { label: '10086积压', value: backlog10086, key: '10086' },
          { label: '全球通积压', value: backlogGlobal, key: 'global' },
          { label: '2200000积压', value: backlog2200000, key: '2200000' },
          { label: '86线下积压', value: backlog86Offline, key: '86_offline' },
        ].map(item => (
          <div key={item.key} style={{
            textAlign: 'center',
            background: '#fafafa',
            borderRadius: 6,
            padding: '6px 4px',
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#374151', lineHeight: 1.2 }}>
              {item.value}
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
              {item.label}
            </div>
          </div>
        ))}
      </div>

      {/* 前一日积压量和环比 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
        <div style={{
          flex: 1,
          background: '#f0fdf4',
          borderRadius: 6,
          padding: '6px 8px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#16a34a', lineHeight: 1.2 }}>
            {previousDayBacklog}
          </div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
            前一日积压量
          </div>
        </div>
        <div style={{
          flex: 1,
          background: '#fef2f2',
          borderRadius: 6,
          padding: '6px 8px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: ratio !== '—' && ratio !== '' && parseFloat(ratio) > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.2 }}>
            {ratio}
          </div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
            环比
          </div>
        </div>
      </div>

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span>点击重新解析 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 企宽故障率专用卡片 ──
function EnterpriseBroadbandFaultCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<EnterpriseBroadbandFaultSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getEnterpriseBroadbandFaultSummary()
      .then(data => setSummary(data as EnterpriseBroadbandFaultSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>企宽故障率</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const faultRate = (() => {
    const raw = summary?.fault_rate
    if (!raw || raw === '—') return '—'
    try {
      const num = parseFloat(raw)
      if (num < 1) return `${(num * 100).toFixed(2)}%`
      return `${num.toFixed(2)}%`
    } catch { return raw }
  })()
  const faultCount = (() => {
    const raw = summary?.fault_count
    if (!raw || raw === '—') return '—'
    try { return String(Math.round(parseFloat(raw))) } catch { return raw }
  })()
  const totalAlarmDuration = (() => {
    const raw = summary?.total_alarm_duration
    if (!raw || raw === '—') return '—'
    try { return parseFloat(raw).toFixed(2) } catch { return raw }
  })()
  const unrecoveredWorkOrders = (() => {
    const raw = summary?.unrecoverd_work_orders
    if (!raw || raw === '—') return '—'
    try { return String(Math.round(parseFloat(raw))) } catch { return raw }
  })()

  return (
    <div
      onClick={() => onNavigate({ name: 'enterprise-broadband-fault-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>企宽故障率</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#ecfdf5',
            color: '#10b981',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 4个核心指标 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 10 }}>
        {[
          { label: '故障率测算', value: faultRate, key: 'fault_rate' },
          { label: '采集故障次数', value: faultCount, key: 'fault_count' },
          { label: '累计告警时长', value: totalAlarmDuration, key: 'total_alarm_duration' },
          { label: '未恢复告警工单', value: unrecoveredWorkOrders, key: 'unrecovered_work_orders' },
        ].map(item => (
          <div key={item.key} style={{
            textAlign: 'center',
            background: '#f0fdf4',
            borderRadius: 8,
            padding: '8px 4px',
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', lineHeight: 1.2 }}>
              {item.value}
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
              {item.label}
            </div>
          </div>
        ))}
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#10b981' }}>点击查看故障明细 →</span>
        </div>
      </div>
    </div>
  )
}


// ── 质差小区弱光工单专用卡片 ──
function PoorQualityWorkOrderCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<PoorQualityWorkOrderSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getPoorQualityWorkOrderSummary()
      .then(data => setSummary(data as PoorQualityWorkOrderSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>质差小区弱光工单</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const workOrderCount = summary?.work_order_count || '—'
  const completedCount = summary?.completed_count || '—'
  const completionRate = (() => {
    const raw = summary?.completion_rate
    if (!raw) return '—'
    const n = parseFloat(raw)
    if (isNaN(n)) return raw
    return (n * 100).toFixed(2) + '%'
  })()
  const communityCount = summary?.community_count || '—'
  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''

  return (
    <div
      onClick={() => onNavigate({ name: 'poor-quality-work-order-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>质差小区弱光工单</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#ecfdf5',
            color: '#10b981',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 核心指标 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 10 }}>
        {[
          { label: '工单数', value: workOrderCount, key: 'work_order_count' },
          { label: '累计回单数', value: completedCount, key: 'completed_count' },
          { label: '完成率', value: completionRate, key: 'completion_rate' },
          { label: '涉及小区数', value: communityCount, key: 'community_count' },
        ].map(item => (
          <div key={item.key} style={{
            textAlign: 'center',
            background: '#f0fdf4',
            borderRadius: 8,
            padding: '8px 4px',
          }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', lineHeight: 1.2 }}>
              {item.value}
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>
              {item.label}
            </div>
          </div>
        ))}
      </div>

      {/* 底部 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#10b981' }}>点击查看未完成明细 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 企宽弱光通报专用卡片 ──
function EnterpriseBroadbandLowLightCard({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<EnterpriseBroadbandLowLightSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getEnterpriseBroadbandLowLightSummary()
      .then(data => setSummary(data as EnterpriseBroadbandLowLightSummary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>企宽弱光通报</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const totalCount = (() => {
    const raw = summary?.total_count
    if (!raw || raw === '—') return '—'
    try { return String(Math.round(parseFloat(raw))) } catch { return raw }
  })()
  const monthlyCompleted = (() => {
    const raw = summary?.monthly_completed
    if (!raw || raw === '—') return '—'
    try { return String(Math.round(parseFloat(raw))) } catch { return raw }
  })()
  const completionRate = (() => {
    const raw = summary?.monthly_completion_rate
    if (!raw || raw === '—') return '—'
    try {
      const n = parseFloat(raw)
      if (n < 1) return `${(n * 100).toFixed(2)}%`
      return `${n.toFixed(2)}%`
    } catch { return raw }
  })()
  const countyRank = summary?.county_rank || '—'
  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''

  return (
    <div
      onClick={() => onNavigate({ name: 'enterprise-broadband-low-light-detail' })}
      style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex', flexDirection: 'column',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>企宽弱光通报</div>
          <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 10, background: '#ecfdf5', color: '#10b981', fontSize: 11, fontWeight: 600 }}>横山</span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>{reportDate || '—'}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 10 }}>
        {[
          { label: '企宽总量', value: totalCount, key: 'total_count' },
          { label: '月完成量', value: monthlyCompleted, key: 'monthly_completed' },
          { label: '月完成率', value: completionRate, key: 'completion_rate' },
          { label: '县区排名', value: countyRank, key: 'county_rank' },
        ].map(item => (
          <div key={item.key} style={{ textAlign: 'center', background: '#f0fdf4', borderRadius: 8, padding: '8px 4px' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a', lineHeight: 1.2 }}>{item.value}</div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>{item.label}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#10b981' }}>点击查看企宽清单 →</span>
        </div>
      </div>
    </div>
  )
}


// ── 10086投诉积压(督办)专用卡片 ──
function Complaint10086Card({ color, onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<Complaint10086Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getComplaint10086Summary()
      .then(data => setSummary(data as Complaint10086Summary))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        display: 'flex', flexDirection: 'column',
        minHeight: 200,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e', marginBottom: 10 }}>10086投诉积压(督办)</div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb', fontSize: 12 }}>
          加载中...
        </div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const totalBacklog = summary?.total_backlog || '—'
  const totalNotOverdue = summary?.total_not_overdue || '—'
  const todayNeedProcess = summary?.today_need_process || '—'
  const broadbandBusiness = summary?.broadband_business || '—'
  const totalOverdue = summary?.total_overdue || '—'
  const warn2hOverdue = summary?.warn_2h_overdue || '—'
  const overdue2_4h = summary?.overdue_2_4h || '—'

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        borderLeft: `4px solid ${color}`,
        transition: 'transform 0.15s, box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
      }}
      onClick={() => onNavigate({ name: 'complaint-10086-detail' })}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)'
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)'
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>10086投诉积压(督办)</div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            background: '#fef2f2',
            color: '#ef4444',
            fontSize: 11,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <span style={{ fontSize: 11, color: '#bbb', whiteSpace: 'nowrap' }}>
          {reportDate || '—'}
        </span>
      </div>

      {/* 合计积压 - 主指标 */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 42, fontWeight: 700, color: totalBacklog !== '—' && parseInt(totalBacklog) > 0 ? '#ef4444' : '#22c55e', lineHeight: 1.1 }}>
          {totalBacklog}
        </div>
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          合计积压
        </div>
      </div>

      {/* 未超时 + 超时 指标 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginBottom: 10 }}>
        <div style={{ textAlign: 'center', background: '#f0fdf4', borderRadius: 6, padding: '6px 4px' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#16a34a', lineHeight: 1.2 }}>{totalNotOverdue}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>合计未超时积压</div>
        </div>
        <div style={{ textAlign: 'center', background: '#fef2f2', borderRadius: 6, padding: '6px 4px' }}>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#ef4444', lineHeight: 1.2 }}>{totalOverdue}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>合计超时积压</div>
        </div>
      </div>

      {/* 今日需处理量 + 家宽业务 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
        <div style={{ flex: 1, background: '#eff6ff', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#2563eb', lineHeight: 1.2 }}>{todayNeedProcess}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>今日需处理量</div>
        </div>
        <div style={{ flex: 1, background: '#fefce8', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#ca8a04', lineHeight: 1.2 }}>{broadbandBusiness}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>家宽业务</div>
        </div>
      </div>

      {/* 剔除夜间 - 预警2小时 + 2-4小时超时 */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
        <div style={{ flex: 1, background: '#fff7ed', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#ea580c', lineHeight: 1.2 }}>{warn2hOverdue}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>预警2小时超时</div>
        </div>
        <div style={{ flex: 1, background: '#fef2f2', borderRadius: 6, padding: '6px 8px', textAlign: 'center' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#dc2626', lineHeight: 1.2 }}>{overdue2_4h}</div>
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>2-4小时超时</div>
        </div>
      </div>

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span>点击查看清单 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 10086投诉积压清单详情页 ──
function Complaint10086DetailPage({ onNavigate }: { onNavigate: (p: Page) => void }) {
  const [records, setRecords] = useState<Complaint10086DetailRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    api.getComplaint10086Details(page, pageSize)
      .then(data => {
        setRecords((data as any).records as Complaint10086DetailRecord[])
        setTotal((data as any).total as number)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

  const columns = [
    { key: 'district', label: '所属区县', width: 80 },
    { key: 'timeout_deadline', label: '超时时限', width: 150 },
    { key: 'broadband_account', label: '宽带帐号', width: 120 },
    { key: 'global_access', label: '全球通属性', width: 100 },
    { key: 'customer_contact', label: '客户联系方式', width: 120 },
    { key: 'customer_urge_count', label: '催单次数', width: 70 },
    { key: 'community_name', label: '小区名称', width: 280 },
    { key: 'handler_name', label: '处理人姓名', width: 90 },
    { key: 'is_door_service', label: '是否上门', width: 70 },
    { key: 'complaint_category5', label: '投诉分类5级', width: 160 },
    { key: 'reply_content', label: '回复内容', width: 400 },
  ]

  return (
    <div style={{ padding: '20px 24px' }}>
      {/* 页面头部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={() => onNavigate({ name: 'dashboard' })}
          style={{
            background: '#f5f5f5', border: 'none', borderRadius: 8,
            padding: '6px 14px', cursor: 'pointer', fontSize: 13, color: '#666',
          }}
        >
          ← 返回
        </button>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#1a1a2e' }}>
          10086投诉积压清单
        </div>
        <span style={{
          display: 'inline-block', padding: '2px 10px', borderRadius: 10,
          background: '#fef2f2', color: '#ef4444', fontSize: 12, fontWeight: 600,
        }}>
          横山
        </span>
        <span style={{ fontSize: 12, color: '#999', marginLeft: 'auto' }}>
          共 {total} 条记录
        </span>
      </div>

      {/* 表格区域 - 可横向滚动 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#bbb' }}>加载中...</div>
      ) : records.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#bbb' }}>暂无数据</div>
      ) : (
        <div style={{
          overflowX: 'auto',
          border: '1px solid #e5e7eb',
          borderRadius: 8,
          background: '#fff',
          WebkitOverflowScrolling: 'touch',
        }}>
          <table style={{ borderCollapse: 'collapse', minWidth: 1700 }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{
                  padding: '10px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                  borderBottom: '2px solid #e5e7eb', textAlign: 'left', whiteSpace: 'nowrap',
                  position: 'sticky', top: 0, background: '#f9fafb', zIndex: 1,
                }}>
                  #
                </th>
                {columns.map(col => (
                  <th key={col.key} style={{
                    padding: '10px 12px', fontSize: 12, fontWeight: 600, color: '#374151',
                    borderBottom: '2px solid #e5e7eb', textAlign: 'left', whiteSpace: 'nowrap',
                    position: 'sticky', top: 0, background: '#f9fafb', zIndex: 1,
                    minWidth: col.width,
                  }}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((rec, idx) => (
                <tr key={rec.id} style={{
                  background: idx % 2 === 0 ? '#fff' : '#fafbfc',
                  borderBottom: '1px solid #f0f0f0',
                }}>
                  <td style={{
                    padding: '8px 12px', fontSize: 12, color: '#999',
                    borderBottom: '1px solid #f0f0f0', whiteSpace: 'nowrap',
                  }}>
                    {(page - 1) * pageSize + idx + 1}
                  </td>
                  {columns.map(col => {
                    const val = (rec as any)[col.key] || ''
                    const isLongText = val.length > 20
                    const isReplyContent = col.key === 'reply_content'
                    const isNotDoor = col.key === 'is_door_service' && val === '否'
                    const textColor = isNotDoor ? '#ef4444' : '#374151'
                    const cellContent = isReplyContent ? (
                      <div style={{ lineHeight: 1.6, wordBreak: 'break-all' }}>
                        {val}
                      </div>
                    ) : isLongText ? (
                      <div style={{
                        lineHeight: 1.5,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 4,
                        WebkitBoxOrient: 'vertical',
                        wordBreak: 'break-all',
                      }}>
                        {val}
                      </div>
                    ) : val
                    return (
                      <td key={col.key} style={{
                        padding: '8px 12px', fontSize: 12, color: textColor,
                        borderBottom: '1px solid #f0f0f0',
                        minWidth: col.width,
                        lineHeight: isReplyContent ? 1.6 : 1.5,
                        whiteSpace: isReplyContent || isLongText ? 'normal' : 'nowrap',
                        wordBreak: 'break-all',
                      }}>
                        {cellContent}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 16 }}>
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => p - 1)}
            style={{
              padding: '6px 14px', border: '1px solid #ddd', borderRadius: 6,
              background: page <= 1 ? '#f5f5f5' : '#fff', cursor: page <= 1 ? 'not-allowed' : 'pointer',
              fontSize: 12, color: page <= 1 ? '#ccc' : '#333',
            }}
          >
            上一页
          </button>
          <span style={{ fontSize: 12, color: '#666' }}>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => p + 1)}
            style={{
              padding: '6px 14px', border: '1px solid #ddd', borderRadius: 6,
              background: page >= totalPages ? '#f5f5f5' : '#fff', cursor: page >= totalPages ? 'not-allowed' : 'pointer',
              fontSize: 12, color: page >= totalPages ? '#ccc' : '#333',
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

// ── 分类报表看板 ──
function ReportTypeCards({ onNavigate }: { onNavigate: (p: Page) => void }) {
  const [reportTypes, setReportTypes] = useState<ReportType[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listReportTypes()
      .then(data => setReportTypes(data as ReportType[]))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>加载报表数据中...</div>
  if (reportTypes.length === 0) return (
    <div style={{ background: '#fff', borderRadius: 10, padding: 24, textAlign: 'center', color: '#999' }}>
      暂无报表数据，请先扫描并解析文件。
    </div>
  )

  // 按分类分组
  const grouped: Record<string, ReportType[]> = {}
  const others: ReportType[] = []

  for (const rt of reportTypes) {
    const cat = classifyReport(rt)
    if (cat) {
      if (!grouped[cat.name]) grouped[cat.name] = []
      grouped[cat.name].push(rt)
    } else {
      others.push(rt)
    }
  }

  return (
    <div>
      {CATEGORIES.map(cat => {
        const items = [...(grouped[cat.name] || [])]
        if (items.length === 0) return null
        // 按 keywords 顺序对 items 排序（keyword 越早出现，排得越靠前）
        items.sort((a, b) => {
          const idxA = cat.keywords.findIndex(kw => a.name.includes(kw))
          const idxB = cat.keywords.findIndex(kw => b.name.includes(kw))
          if (idxA === -1) return 1
          if (idxB === -1) return -1
          return idxA - idxB
        })
        return (
          <div key={cat.name} style={{ marginBottom: 32 }}>
            <h3 style={{
              fontSize: 16,
              fontWeight: 600,
              color: '#1a1a2e',
              margin: '0 0 16px 0',
              paddingBottom: 8,
              borderBottom: `2px solid ${cat.color}`,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <span style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: cat.color,
              }} />
              {cat.name}
              <span style={{ fontSize: 12, color: '#888', fontWeight: 400, marginLeft: 8 }}>
                共 {items.length} 种报表
              </span>
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {items.map(rt => {
                // 无线退服清单用专用卡片
                if (rt.name === '无线退服清单') {
                  return <WirelessOutageCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 皮站故障清单用专用卡片
                if (rt.name === '皮站故障清单') {
                  return <PisiteFaultCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 接入层通报用专用卡片
                if (rt.name === '接入层通报') {
                  return <AccessLayerFaultCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 企宽装机通报用专用卡片
                if (rt.name === '企宽装机通报') {
                  return <EnterpriseBroadbandCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 日用专用卡片
                if (rt.name === '日报') {
                  return <DailyReportCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 全市装维工作量统计用专用卡片
                if (rt.name === '全市装维工作量统计') {
                  return <CityWorkloadCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 五类工单退撤单情况用专用卡片
                if (rt.name === '五类工单退撤单情况') {
                  return <FiveCategoryWithdrawalCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 宽带在途投诉清单用专用卡片
                if (rt.name === '宽带在途投诉清单') {
                  return <ComplaintBacklogCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 企宽故障率用专用卡片
                if (rt.name === '企宽故障率') {
                  return <EnterpriseBroadbandFaultCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 企宽弱光通报用专用卡片
                if (rt.name === '企宽弱光通报') {
                  return <EnterpriseBroadbandLowLightCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 质差小区弱光工单处理完成率用专用卡片
                if (rt.name === '质差小区弱光工单处理完成率') {
                  return <PoorQualityWorkOrderCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 10086投诉积压(督办)用专用卡片
                if (rt.name === '10086投诉积压(督办)') {
                  return <Complaint10086Card key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 2200000及时率通报用专用卡片
                if (rt.name === '2200000及时率通报') {
                  return <Complaint2200000Card key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 家宽重投2次清单用专用卡片
                if (rt.name === '家宽重投2次清单明细') {
                  return <BroadbandRedelivery2Card key={rt.id} color={cat.color} />
                }
                // 线下派单处理情况用专用卡片
                if (rt.name === '线下派单处理情况') {
                  return <OfflineDispatchCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                // 重投预警工单梳理用专用卡片
                if (rt.name === '重投预警工单梳理') {
                  return <RetryWarningCard key={rt.id} color={cat.color} onNavigate={onNavigate} />
                }
                return <ReportCard key={rt.id} rt={rt} color={cat.color} onNavigate={onNavigate} />
              })}
            </div>
          </div>
        )
      })}

      {/* 未分类的报表 */}
      {others.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <h3 style={{
            fontSize: 16,
            fontWeight: 600,
            color: '#1a1a2e',
            margin: '0 0 16px 0',
            paddingBottom: 8,
            borderBottom: '2px solid #888',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{
              display: 'inline-block',
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: '#888',
            }} />
            其他报表
            <span style={{ fontSize: 12, color: '#888', fontWeight: 400, marginLeft: 8 }}>
              共 {others.length} 种报表
            </span>
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
            {others.map(rt => (
              <ReportCard key={rt.id} rt={rt} color="#888" onNavigate={onNavigate} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── 2200000及时率通报 卡片 ──
function Complaint2200000Card({ onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<Complaint2200000Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    ;(api as any).getComplaint2200000Summary()
      .then((data: Complaint2200000Summary) => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const monthlyDispatch = summary?.monthly_dispatch || '—'
  const overdueBacklog = summary?.overdue_backlog || '—'
  const notOverdueBacklog = summary?.not_overdue_backlog || '—'
  const totalInTransit = summary?.total_in_transit || '—'
  const previousMonthBacklog = summary?.previous_month_backlog || '—'
  const warn4hOverdue = summary?.warn_4h_overdue || '—'
  const escalateComplaint = summary?.escalate_complaint || '—'

  return (
    <div
      onClick={() => onNavigate({ name: 'complaint-2200000-detail' })}
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s',
        minWidth: 260,
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e' }}>2200000及时率通报</span>
        {reportDate && (
          <span style={{ fontSize: 11, color: '#999' }}>{reportDate.slice(5)}</span>
        )}
      </div>

      {/* 月派单量 - 大数字 */}
      <div style={{ textAlign: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: '#2563eb', lineHeight: 1.1 }}>
          {loading ? '...' : monthlyDispatch}
        </div>
        <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>月派单量</div>
      </div>

      {/* 在途积压 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, background: '#fef2f2', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#dc2626' }}>{overdueBacklog}</div>
          <div style={{ fontSize: 9, color: '#888' }}>超时积压</div>
        </div>
        <div style={{ flex: 1, background: '#f0fdf4', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#16a34a' }}>{notOverdueBacklog}</div>
          <div style={{ fontSize: 9, color: '#888' }}>未超时积压</div>
        </div>
        <div style={{ flex: 1, background: '#eff6ff', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#2563eb' }}>{totalInTransit}</div>
          <div style={{ fontSize: 9, color: '#888' }}>累计在途</div>
        </div>
      </div>

      {/* 预警4h超时 */}
      <div style={{ marginBottom: 6, background: '#fff7ed', borderRadius: 6, padding: '4px 6px', textAlign: 'center' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#ea580c' }}>{warn4hOverdue}</div>
        <div style={{ fontSize: 9, color: '#888' }}>预警4h超时</div>
      </div>

      {/* 升级投诉量 */}
      <div style={{ textAlign: 'center', padding: '4px 0 0', borderTop: '1px solid #f0f0f0' }}>
        <span style={{ fontSize: 11, color: '#888' }}>升级投诉量: </span>
        <span style={{ fontSize: 15, fontWeight: 700, color: '#dc2626' }}>{escalateComplaint}</span>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '6px 0 0', fontSize: 11, color: '#bbb' }}>加载中...</div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看清单 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 家宽重投2次 卡片 ──
function BroadbandRedelivery2Card({ color }: { color: string }) {
  const [summary, setSummary] = useState<BroadbandRedelivery2Summary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    ;(api as any).getBroadbandRedelivery2Summary()
      .then((data: BroadbandRedelivery2Summary) => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        background: '#fff', borderRadius: 12, padding: '16px 20px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)', minWidth: 260,
      }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e' }}>家宽重投2次</div>
        <div style={{ textAlign: 'center', padding: 20, color: '#bbb', fontSize: 13 }}>加载中...</div>
      </div>
    )
  }

  const reportDate = summary?.report_date || ''
  const latestFilename = summary?.latest_filename || ''
  const timePeriod = summary?.time_period || ''

  const metrics = [
    { label: '重投2次在途量', value: summary?.redelivery2_in_transit || '—', bg: '#fef2f2', color: '#dc2626' },
    { label: '2次全球通量', value: summary?.global_tong_2 || '—', bg: '#fff7ed', color: '#ea580c' },
    { label: '重投3次', value: summary?.redelivery3 || '—', bg: '#fef2f2', color: '#dc2626' },
    { label: '3次全球通量', value: summary?.global_tong_3 || '—', bg: '#fff7ed', color: '#ea580c' },
    { label: '重投4次及以上', value: summary?.redelivery4_plus || '—', bg: '#fef2f2', color: '#dc2626' },
    { label: '4次全球通量', value: summary?.global_tong_4 || '—', bg: '#fff7ed', color: '#ea580c' },
    { label: '总在途重投量', value: summary?.total_in_transit || '—', bg: '#eff6ff', color: '#2563eb' },
    { label: '重投2次处理量', value: summary?.redelivery2_processed || '—', bg: '#f0fdf4', color: '#16a34a' },
  ]

  return (
    <div style={{
      background: '#fff',
      borderRadius: 12,
      padding: '16px 20px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      minWidth: 260,
    }}>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e' }}>家宽重投2次</span>
          <span style={{
            fontSize: 10, background: '#dbeafe', color: '#2563eb',
            padding: '2px 6px', borderRadius: 4, fontWeight: 500,
          }}>横山</span>
        </div>
        <span style={{ fontSize: 11, color: '#999' }}>
          {reportDate ? `${reportDate.slice(5)} ${timePeriod}` : ''}
        </span>
      </div>

      {/* 8项指标 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
        {metrics.map((m, i) => (
          <div key={i} style={{
            background: m.bg,
            borderRadius: 6,
            padding: '6px 8px',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: m.color, lineHeight: 1.2 }}>
              {m.value}
            </div>
            <div style={{ fontSize: 10, color: '#888', marginTop: 1 }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
        </div>
      </div>
    </div>
  )
}

// ── 线下派单处理情况 卡片 ──
function OfflineDispatchCard({ onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<OfflineDispatchSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    ;(api as any).getOfflineDispatchSummary()
      .then((data: OfflineDispatchSummary) => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const monthlyDispatch = summary?.monthly_dispatch || '—'
  const overdueBacklog = summary?.overdue_backlog || '—'
  const notOverdueBacklog = summary?.not_overdue_backlog || '—'
  const totalInTransit = summary?.total_in_transit || '—'
  const warn4hOverdue = summary?.warn_4h_overdue || '—'

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s',
        minWidth: 260,
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
      onClick={() => onNavigate({ name: 'offline-dispatch-detail' })}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e' }}>线下派单处理情况</span>
        {reportDate && (
          <span style={{ fontSize: 11, color: '#999' }}>{reportDate.slice(5)}</span>
        )}
      </div>

      {/* 月派单量 - 大数字 */}
      <div style={{ textAlign: 'center', marginBottom: 10 }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: '#2563eb', lineHeight: 1.1 }}>
          {loading ? '...' : monthlyDispatch}
        </div>
        <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>月派单量</div>
      </div>

      {/* 在途积压(24h) */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, background: '#fef2f2', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#dc2626' }}>{overdueBacklog}</div>
          <div style={{ fontSize: 9, color: '#888' }}>超时积压</div>
        </div>
        <div style={{ flex: 1, background: '#f0fdf4', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#16a34a' }}>{notOverdueBacklog}</div>
          <div style={{ fontSize: 9, color: '#888' }}>未超时积压</div>
        </div>
        <div style={{ flex: 1, background: '#eff6ff', borderRadius: 6, padding: '4px 6px', textAlign: 'center', minWidth: 70 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#2563eb' }}>{totalInTransit}</div>
          <div style={{ fontSize: 9, color: '#888' }}>累计在途</div>
        </div>
      </div>

      {/* 预警4h超时 */}
      <div style={{ background: '#fff7ed', borderRadius: 6, padding: '4px 6px', textAlign: 'center' }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#ea580c' }}>{warn4hOverdue}</div>
        <div style={{ fontSize: 9, color: '#888' }}>预警4h超时</div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '6px 0 0', fontSize: 11, color: '#bbb' }}>加载中...</div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看清单 →</span>
        </div>
      </div>
    </div>
  )
}

// ── 重投预警工单梳理 卡片 ──
function RetryWarningCard({ onNavigate }: { color: string; onNavigate: (p: Page) => void }) {
  const [summary, setSummary] = useState<RetryWarningSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    ;(api as any).getRetryWarningSummary()
      .then((data: RetryWarningSummary) => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const reportDate = summary?.report_date || ''
  const latestFilename = (summary as any)?.latest_filename || ''
  const r2 = summary?.retry_2_times || '—'
  const r3 = summary?.retry_3_times || '—'
  const r4 = summary?.retry_4plus_times || '—'
  const total = summary?.total_in_transit || '—'
  const dailyClosed = summary?.daily_closed || '—'
  const repairTotal = summary?.repair_total || '—'
  const repairInTransit = summary?.repair_in_transit || '—'
  const repairClosed = summary?.repair_closed || '—'

  return (
    <div
      style={{
        background: '#fff',
        borderRadius: 12,
        padding: '16px 20px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s',
        minWidth: 320,
      }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.08)')}
      onClick={() => onNavigate({ name: 'retry-warning-detail' })}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e' }}>重投预警工单梳理</span>
        {reportDate && (
          <span style={{ fontSize: 11, color: '#999' }}>{reportDate.slice(5)}</span>
        )}
      </div>

      {/* 重投86预警 */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 6, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          重投86预警
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, marginBottom: 4 }}>
          {[
            { label: '2次在途', value: r2, color: '#f59e0b' },
            { label: '3次在途', value: r3, color: '#f97316' },
            { label: '4次+在途', value: r4, color: '#ef4444' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center', background: '#fffbeb', borderRadius: 6, padding: '6px 2px' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: item.color, lineHeight: 1.2 }}>{loading ? '...' : item.value}</div>
              <div style={{ fontSize: 9, color: '#888', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 4 }}>
          {[
            { label: '总在途', value: total, color: '#2563eb' },
            { label: '日闭环', value: dailyClosed, color: '#16a34a' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center', background: '#f0f9ff', borderRadius: 6, padding: '6px 2px' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: item.color, lineHeight: 1.2 }}>{loading ? '...' : item.value}</div>
              <div style={{ fontSize: 9, color: '#888', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 客户催修 */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#666', marginBottom: 6, borderBottom: '1px solid #f0f0f0', paddingBottom: 4 }}>
          客户催修
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
          {[
            { label: '催修量', value: repairTotal, color: '#7c3aed' },
            { label: '在途催修', value: repairInTransit, color: '#ea580c' },
            { label: '闭环量', value: repairClosed, color: '#16a34a' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center', background: '#faf5ff', borderRadius: 6, padding: '6px 2px' }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: item.color, lineHeight: 1.2 }}>{loading ? '...' : item.value}</div>
              <div style={{ fontSize: 9, color: '#888', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '6px 0 0', fontSize: 11, color: '#bbb' }}>加载中...</div>
      )}

      {/* 底部信息 */}
      <div style={{ fontSize: 11, color: '#aaa', borderTop: '1px solid #f5f5f5', paddingTop: 8, marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }} title={latestFilename}>
            📄 {latestFilename || (reportDate ? `通报 ${reportDate}` : '—')}
          </span>
          <span style={{ color: '#3b82f6' }}>点击查看清单 →</span>
        </div>
      </div>
    </div>
  )
}


// ── 2200000及时率通报 详情页 ──
function Complaint2200000DetailPage({ onNavigate }: { onNavigate: (p: Page) => void }) {
  const [records, setRecords] = useState<Complaint2200000DetailRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    ;(api as any).getComplaint2200000Details(page, pageSize)
      .then((data: any) => {
        setRecords(data.records as Complaint2200000DetailRecord[])
        setTotal(data.total as number)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

  const columns = [
    { key: 'district', label: '所属区县', width: '5%', align: 'center' as const },
    { key: 'timeout_deadline', label: '超时时限', width: '13%', align: 'left' as const },
    { key: 'broadband_account', label: '宽带帐号', width: '9%', align: 'center' as const },
    { key: 'is_important_customer', label: '是否重要客户', width: '7%', align: 'center' as const },
    { key: 'customer_contact', label: '客户联系方式', width: '11%', align: 'left' as const },
    { key: 'construction_address', label: '施工地址', width: '37%', align: 'left' as const },
    { key: 'handler_name', label: '处理人姓名', width: '6%', align: 'center' as const },
    { key: 'category', label: '分类', width: '5%', align: 'center' as const },
  ]

  return (
    <div style={{ padding: '20px 24px' }}>
      {/* 页面头部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={() => onNavigate({ name: 'dashboard' })}
          style={{
            padding: '6px 14px',
            borderRadius: 6,
            border: '1px solid #ddd',
            background: '#fff',
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          ← 返回
        </button>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#1a1a2e' }}>
          2200000投诉积压清单
        </div>
        <span style={{
          display: 'inline-block', padding: '2px 10px', borderRadius: 10,
          background: '#f0fdf4', color: '#16a34a', fontSize: 12, fontWeight: 600,
        }}>
          横山
        </span>
        <span style={{ fontSize: 12, color: '#999', marginLeft: 'auto' }}>
          共 {total} 条记录
        </span>
      </div>

      {/* 数据表格 */}
      <div style={{
        background: '#fff',
        borderRadius: 12,
        padding: '20px 24px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中...</div>
        ) : records.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
            <div style={{ fontSize: 16, color: '#999' }}>暂无数据</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 900, fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #eee' }}>
                  <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#666', whiteSpace: 'nowrap' }}>#</th>
                  {columns.map(col => (
                    <th key={col.key} style={{
                      padding: '8px 10px', fontWeight: 600, color: '#666',
                      textAlign: 'left', whiteSpace: 'nowrap',
                    }}>
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {records.map((rec, idx) => (
                  <tr key={rec.id} style={{ background: idx % 2 === 0 ? '#fff' : '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                    <td style={{ padding: '6px 10px', color: '#aaa' }}>{(page - 1) * pageSize + idx + 1}</td>
                    {columns.map(col => {
                    const val = (rec as any)[col.key] || ''
                    const isAddress = col.key === 'construction_address'

                    // 重点标注：是否重要客户=是 → 橙色文字
                    const isImportant = col.key === 'is_important_customer' && val === '是'
                    // 分类颜色区分：往月=黄色标签，在途=蓝色标签
                    const isPrevMonth = col.key === 'category' && val === '往月'
                    const isInTransit = col.key === 'category' && val === '在途'

                    const cellStyle: React.CSSProperties = {
                      padding: '6px 10px',
                      whiteSpace: isAddress ? 'normal' : 'nowrap',
                      maxWidth: 200,
                      overflow: isAddress ? 'hidden' : 'hidden',
                      textOverflow: isAddress ? undefined : 'ellipsis',
                      wordBreak: 'break-word',
                    }

                    let cellContent: React.ReactNode
                    if (isAddress) {
                      cellContent = (
                        <div style={{ lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', wordBreak: 'break-word' }} title={String(val)}>
                          {val}
                        </div>
                      )
                    } else if (isImportant) {
                      cellContent = (
                        <span style={{ color: '#f59e0b', fontWeight: 600 }}>{val}</span>
                      )
                    } else if (isPrevMonth) {
                      cellContent = (
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: '#fef3c7',
                          color: '#92400e',
                          fontSize: 12,
                          fontWeight: 500,
                        }}>{val}</span>
                      )
                    } else if (isInTransit) {
                      cellContent = (
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 4,
                          background: '#dbeafe',
                          color: '#1e40af',
                          fontSize: 12,
                          fontWeight: 500,
                        }}>{val}</span>
                      )
                    } else {
                      cellContent = <span>{val}</span>
                    }

                    return (
                      <td key={col.key} style={cellStyle} title={String((rec as any)[col.key] ?? '')}>
                        {cellContent}
                      </td>
                    )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16, alignItems: 'center' }}>
          <button
            disabled={page <= 1}
            onClick={() => setPage(p => Math.max(1, p - 1))}
            style={{
              padding: '4px 12px', borderRadius: 6, border: '1px solid #d1d5db',
              background: page <= 1 ? '#f5f5f5' : '#fff', cursor: page <= 1 ? 'not-allowed' : 'pointer',
            }}
          >上一页</button>
          <span style={{ fontSize: 13, color: '#666' }}>{page} / {totalPages}</span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            style={{
              padding: '4px 12px', borderRadius: 6, border: '1px solid #d1d5db',
              background: page >= totalPages ? '#f5f5f5' : '#fff', cursor: page >= totalPages ? 'not-allowed' : 'pointer',
            }}
          >下一页</button>
        </div>
      )}
    </div>
  )
}

// ── 通知铃铛组件 ──

function NotificationBell() {
  const [notifications, setNotifications] = useState<import('../types').Notification[]>([])
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  const fetchNotifications = () => {
    api.getNotifications(10)
      .then((data: import('../types').Notification[]) => {
        setNotifications(data)
        setUnreadCount(data.filter(n => !n.is_read).length)
      })
      .catch(() => {})
  }

  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleMarkAllRead = () => {
    api.markAllNotificationsRead()
      .then(() => {
        setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
        setUnreadCount(0)
      })
      .catch(() => {})
  }

  const formatTime = (iso: string) => {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          position: 'relative',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        title="通知"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: 2,
            right: 2,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: '#ef4444',
            color: '#fff',
            fontSize: 10,
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <>
          <div
            style={{
              position: 'fixed',
              top: 0, left: 0, right: 0, bottom: 0,
              zIndex: 40,
            }}
            onClick={() => setOpen(false)}
          />
          <div style={{
            position: 'absolute',
            top: 44,
            right: 0,
            width: 360,
            maxHeight: 420,
            background: '#fff',
            borderRadius: 12,
            boxShadow: '0 10px 40px rgba(0,0,0,0.15)',
            zIndex: 50,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}>
            {/* 头部 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: '1px solid #f0f0f0',
            }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>指标更新通知</span>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#3b82f6',
                    fontSize: 12,
                    cursor: 'pointer',
                  }}
                >
                  全部已读
                </button>
              )}
            </div>

            {/* 列表 */}
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {notifications.length === 0 ? (
                <div style={{ padding: 32, textAlign: 'center', color: '#999', fontSize: 13 }}>
                  暂无更新通知
                </div>
              ) : (
                notifications.map(n => (
                  <div
                    key={n.id}
                    style={{
                      padding: '10px 16px',
                      borderBottom: '1px solid #f5f5f5',
                      background: n.is_read ? '#fff' : '#f0f9ff',
                      cursor: 'pointer',
                    }}
                    onClick={() => {
                      if (!n.is_read) {
                        api.markNotificationRead(n.id)
                          .then(() => {
                            setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, is_read: true } : x))
                            setUnreadCount(c => Math.max(0, c - 1))
                          })
                          .catch(() => {})
                      }
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: n.is_read ? '#ccc' : '#3b82f6',
                        flexShrink: 0,
                      }} />
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#333' }}>
                        {n.report_type}
                      </span>
                      <span style={{ fontSize: 11, color: '#aaa', marginLeft: 'auto' }}>
                        {formatTime(n.event_time)}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#666', paddingLeft: 14 }}>
                      来源：{n.filename}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export function Dashboard({ onNavigate, initialPage }: { onNavigate: (p: Page) => void; initialPage?: string }) {
  // 如果指定了initialPage且是10086投诉积压详情页，直接展示详情页
  if (initialPage === 'complaint-10086-detail') {
    return <Complaint10086DetailPage onNavigate={onNavigate} />
  }
  // 2200000及时率通报详情页
  if (initialPage === 'complaint-2200000-detail') {
    return <Complaint2200000DetailPage onNavigate={onNavigate} />
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>横山网络指标通报</h2>
        <NotificationBell />
      </div>
      <ReportTypeCards onNavigate={onNavigate} />
    </div>
  )
}
