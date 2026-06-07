import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { EnterpriseBroadbandFaultSummary, EnterpriseBroadbandFaultRecord } from '../types'

const DISPLAY_FIELDS = [
  { key: 'district', label: '区县', width: '80px' },
  { key: 'olt_name', label: 'OLT名称', width: '140px' },
  { key: 'olt_ip', label: 'OLT-IP', width: '130px' },
  { key: 'pon_port', label: 'PON口', width: '120px' },
  { key: 'account', label: '账号', width: '130px' },
  { key: 'alarm_total', label: '告警累计', width: '100px', sortable: true },
  { key: 'alarm_weighted_duration', label: '告警加权时长', width: '120px', sortable: true },
]

type SortField = 'alarm_total' | 'alarm_weighted_duration' | ''
type SortOrder = 'asc' | 'desc'

export function EnterpriseBroadbandFaultDetail({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<EnterpriseBroadbandFaultRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<EnterpriseBroadbandFaultSummary | null>(null)
  const [sortField, setSortField] = useState<SortField>('')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [districtFilter, setDistrictFilter] = useState('')
  const pageSize = 50

  const fetchData = () => {
    setLoading(true)
    Promise.all([
      api.getEnterpriseBroadbandFaultSummary(),
      api.getEnterpriseBroadbandFaultDetails({
        page,
        page_size: pageSize,
        sort_field: sortField || undefined,
        sort_order: sortField ? sortOrder : undefined,
        district: districtFilter || undefined,
      }),
    ])
      .then(([summaryData, detailData]) => {
        setSummary(summaryData as EnterpriseBroadbandFaultSummary)
        setRecords(detailData.records as unknown as EnterpriseBroadbandFaultRecord[])
        setTotal(detailData.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchData()
  }, [page, sortField, sortOrder, districtFilter])

  const totalPages = Math.ceil(total / pageSize)

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
    setPage(1)
  }

  return (
    <div>
      {/* 顶部标题栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 20,
        padding: '16px 20px',
        background: '#fff',
        borderRadius: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={onBack}
            style={{
              background: 'none',
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              padding: '6px 12px',
              cursor: 'pointer',
              fontSize: 13,
              color: '#666',
            }}
          >
            ← 返回
          </button>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1a1a2e', margin: 0 }}>
            企宽故障率明细
          </h2>
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            background: '#ecfdf5',
            color: '#10b981',
            fontSize: 12,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>故障率测算</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a' }}>
              {(() => {
                const raw = summary?.fault_rate
                if (!raw) return '—'
                try {
                  const num = parseFloat(raw)
                  if (num < 1) return `${(num * 100).toFixed(2)}%`
                  return `${num.toFixed(2)}%`
                } catch { return raw }
              })()}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>采集故障次数</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>
              {summary?.fault_count || '—'}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>通报日期</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#666' }}>
              {summary?.report_date || '—'}
            </div>
          </div>
        </div>
      </div>

      {/* 筛选栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 16,
        padding: '12px 16px',
        background: '#fff',
        borderRadius: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        <span style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>区县筛选：</span>
        <input
          type="text"
          placeholder="输入区县名称（如：横山）"
          value={districtFilter}
          onChange={e => { setDistrictFilter(e.target.value); setPage(1) }}
          style={{
            padding: '6px 12px',
            borderRadius: 6,
            border: '1px solid #e5e7eb',
            fontSize: 13,
            width: 200,
            outline: 'none',
          }}
        />
        {districtFilter && (
          <button
            onClick={() => { setDistrictFilter(''); setPage(1) }}
            style={{
              background: 'none',
              border: '1px solid #e5e7eb',
              borderRadius: 6,
              padding: '4px 10px',
              cursor: 'pointer',
              fontSize: 12,
              color: '#888',
            }}
          >
            清除
          </button>
        )}
        <span style={{ fontSize: 12, color: '#aaa', marginLeft: 'auto' }}>
          共 {total} 条记录
        </span>
      </div>

      {/* 数据表格 */}
      {loading ? (
        <div style={{
          background: '#fff',
          borderRadius: 10,
          padding: 40,
          textAlign: 'center',
          color: '#bbb',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}>
          加载中...
        </div>
      ) : (
        <div style={{
          background: '#fff',
          borderRadius: 10,
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
          overflow: 'hidden',
        }}>
          {records.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
              暂无故障数据
            </div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 13,
                  minWidth: 820,
                }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e5e7eb' }}>
                      {DISPLAY_FIELDS.map(f => (
                        <th
                          key={f.key}
                          onClick={() => f.sortable && handleSort(f.key as SortField)}
                          style={{
                            padding: '10px 12px',
                            textAlign: 'left',
                            color: '#374151',
                            fontWeight: 600,
                            fontSize: 12,
                            whiteSpace: 'nowrap',
                            width: f.width,
                            cursor: f.sortable ? 'pointer' : 'default',
                            userSelect: f.sortable ? 'none' : 'auto',
                          }}
                        >
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            {f.label}
                            {f.sortable && sortField === f.key && (
                              <span style={{ fontSize: 10, color: '#10b981', fontWeight: 700 }}>
                                {sortOrder === 'asc' ? '↑' : '↓'}
                              </span>
                            )}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((rec, idx) => (
                      <tr
                        key={rec.id}
                        style={{
                          background: idx % 2 === 0 ? '#fff' : '#fafafa',
                          borderBottom: '1px solid #f0f0f0',
                        }}
                      >
                        {DISPLAY_FIELDS.map(f => {
                          const val = (rec as unknown as Record<string, string>)[f.key] || ''
                          return (
                            <td key={f.key} style={{
                              padding: '8px 12px',
                              color: '#333',
                              maxWidth: f.width,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }} title={val}>
                              {val || '—'}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 分页器 */}
              {totalPages > 1 && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: 8,
                  padding: '16px 0',
                  borderTop: '1px solid #f0f0f0',
                }}>
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 6,
                      border: '1px solid #e5e7eb',
                      background: page <= 1 ? '#f5f5f5' : '#fff',
                      color: page <= 1 ? '#ccc' : '#333',
                      cursor: page <= 1 ? 'not-allowed' : 'pointer',
                      fontSize: 13,
                    }}
                  >
                    上一页
                  </button>
                  <span style={{ fontSize: 13, color: '#666' }}>
                    第 {page} / {totalPages} 页（共 {total} 条）
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    style={{
                      padding: '6px 14px',
                      borderRadius: 6,
                      border: '1px solid #e5e7eb',
                      background: page >= totalPages ? '#f5f5f5' : '#fff',
                      color: page >= totalPages ? '#ccc' : '#333',
                      cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                      fontSize: 13,
                    }}
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
