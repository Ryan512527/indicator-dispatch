import { useState, useEffect } from 'react'
import { api } from '../services/api'

const CN_MAP: Record<string, string> = {
  // 无线退服基站
  station_type: '基站类型',
  site_name: '站址名称',
  alarm_name: '告警名称',
  alarm_time: '告警时间',
  outage_duration_hours: '退服时长(h)',
  guarantee_scenario: '保障场景',
  guarantee_time_limit: '保障时限(小时)',
  is_timeout: '是否超时',
  is_tower_maintenance: '是否塔维',
  // 接入层故障
  fiber_break_link: '断纤链路',
  occurrence_time: '发生时间',
  specific_reason: '具体原因',
  business_affected: '是否影响业务',
  fault_duration: '故障历时',
  alarm_code_name: '告警码名称',
  responsible_person: '责任人',
}

function fmt(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function OutageDetail({ params, onBack }: {
  params: Record<string, string>
  onBack: () => void
}) {
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const category = params.category || '无线退服'

  useEffect(() => {
    api.queryEvents({
      category: category,
      start: params.start || undefined,
      end: params.end || undefined,
      limit: '500',
    }).then(setEvents).catch(console.error).finally(() => setLoading(false))
  }, [params.start, params.end, category])

  const title = category === '接入层故障' ? '接入层故障清单' : '退服基站清单'

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button onClick={onBack} style={{
          padding: '6px 14px', borderRadius: 6, border: '1px solid #ddd',
          background: '#fff', cursor: 'pointer', fontSize: 14,
        }}>
          &larr; 返回
        </button>
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>{title}</h2>
        <span style={{ fontSize: 13, color: '#999' }}>
          {params.title || ''} &middot; {loading ? '加载中...' : `${events.length} 条记录`}
        </span>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', paddingTop: 60, color: '#999' }}>加载中...</div>
      ) : events.length === 0 ? (
        <div style={{ textAlign: 'center', paddingTop: 60, color: '#999' }}>
          该时段没有记录
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {events.map((evt: any) => {
            const dim = evt.dimensions || {}
            const isAccess = category === '接入层故障'

            // Which fields to show depends on category
            const fieldKeys = isAccess
              ? ['fiber_break_link', 'specific_reason', 'occurrence_time', 'business_affected', 'fault_duration', 'alarm_code_name', 'responsible_person']
              : ['site_name', 'alarm_name', 'station_type', 'alarm_time', 'outage_duration_hours', 'guarantee_scenario', 'guarantee_time_limit', 'is_timeout', 'is_tower_maintenance']

            const fields = fieldKeys.map(k => ({
              k,
              v: k === 'outage_duration_hours' ? Math.round(evt.value * 10) / 10
                : k === 'fault_duration' ? (dim[k] ? Number(parseFloat(dim[k]).toFixed(1)) : '') + ' 小时' : k === 'outage_duration_hours' ? Math.round(evt.value * 10) / 10
                : dim[k],
            })).filter(f => f.v != null && f.v !== '')

            return (
              <div key={evt.id} style={{
                background: '#fff', borderRadius: 10, padding: '14px 18px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                border: `1px solid ${isAccess ? '#fef3c7' : '#f0f0f0'}`,
                borderLeft: `3px solid ${isAccess ? '#f59e0b' : '#ef4444'}`,
              }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, color: '#1a1a2e' }}>
                  {isAccess
                    ? (dim.fiber_break_link || '接入层故障')
                    : (dim.site_name || '未知站点')}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', fontSize: 13, color: '#555' }}>
                  {fields.map(f => (
                    <span key={f.k}>
                      <span style={{ color: '#999' }}>{CN_MAP[f.k] || f.k}:</span>{' '}
                      <strong>{String(f.v)}</strong>
                    </span>
                  ))}
                </div>
                <div style={{ marginTop: 6, fontSize: 11, color: '#bbb' }}>
                  {evt.source}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
