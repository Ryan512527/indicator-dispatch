import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { Page, ReportType, WirelessOutageSummary, PisiteFaultSummary } from '../types'

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
    keywords: ['企宽装机通报', '日报', '成功率攻坚通报', '全市装维工作量统计', '家宽+FTTR遗留工单安装进度通报', 'H5当日闭环测评清单', '企宽开通及时率通报', '五类工单退撤单情况', '触点用后即评'],
  },
  {
    name: '第三类：投诉类',
    color: '#f59e0b',
    keywords: ['宽带在途投诉清单', '家宽重投2次清单明细', '投诉积压通报新', '重投预警工单梳理', '2200000及时率通报', '线下派单处理情况', '投诉积压大于3单人员通报', '投诉三类工单在途情况'],
  },
  {
    name: '第四类：质差整治类',
    color: '#10b981',
    keywords: ['质差客户整治完成率通报', '质差小区弱光工单处理完成率', '企宽故障率', '一二级分支真实处理通报', '一户一案'],
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
        const items = grouped[cat.name] || []
        if (items.length === 0) return null
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

export function Dashboard({ onNavigate }: { onNavigate: (p: Page) => void }) {
  return (
    <div>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24 }}>横山网络指标通报</h2>
      <ReportTypeCards onNavigate={onNavigate} />
    </div>
  )
}
