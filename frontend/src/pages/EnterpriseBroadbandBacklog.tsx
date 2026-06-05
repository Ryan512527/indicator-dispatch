import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { EnterpriseBroadbandBacklogRecord } from '../types'

const DISPLAY_FIELDS = [
  { key: 'district', label: '所属区县', width: '80px' },
  { key: 'account', label: '宽带账号', width: '130px' },
  { key: 'address', label: '施工地址', width: '280px' },
  { key: 'worker_name', label: '施工人姓名', width: '90px' },
  { key: 'accept_time', label: '受理时间', width: '150px' },
  { key: 'to_install_time', label: '到装维时间', width: '150px' },
  { key: 'deadline', label: '完成时限', width: '150px' },
  { key: 'install_duration_hours', label: '装机历时（h）', width: '110px' },
  { key: 'user_brand', label: '用户品牌', width: '110px' },
]

export function EnterpriseBroadbandBacklog({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<EnterpriseBroadbandBacklogRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<{
    total_backlog?: string
    day_backlog?: string
    report_date?: string
  }>({})
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getEnterpriseBroadbandSummary(),
      api.getEnterpriseBroadbandBacklog(page, pageSize),
    ])
      .then(([summaryData, backlogData]) => {
        setSummary(summaryData as typeof summary)
        setRecords(backlogData.records)
        setTotal(backlogData.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

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
            企宽积压清单
          </h2>
          <span style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 10,
            background: '#eff6ff',
            color: '#3b82f6',
            fontSize: 12,
            fontWeight: 600,
          }}>
            横山
          </span>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>当日积压</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>
              {summary.day_backlog || '—'}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>积压总量</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#1e40af' }}>
              {summary.total_backlog || '—'}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>通报日期</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#666' }}>
              {summary.report_date || '—'}
            </div>
          </div>
        </div>
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
              暂无积压数据
            </div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 13,
                  minWidth: 1200,
                }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e5e7eb' }}>
                      {DISPLAY_FIELDS.map(f => (
                        <th key={f.key} style={{
                          padding: '10px 12px',
                          textAlign: 'left',
                          color: '#374151',
                          fontWeight: 600,
                          fontSize: 12,
                          whiteSpace: 'nowrap',
                          width: f.width,
                        }}>
                          {f.label}
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
                          // 装机历时高亮展示
                          const isDuration = f.key === 'install_duration_hours'
                          const durationNum = isDuration ? parseFloat(val) : NaN
                          return (
                            <td key={f.key} style={{
                              padding: '8px 12px',
                              color: '#333',
                              maxWidth: f.width,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: f.key === 'address' ? 'normal' : 'nowrap',
                            }} title={val}>
                              {val || '—'}
                              {isDuration && !isNaN(durationNum) && durationNum > 48 && (
                                <span style={{
                                  marginLeft: 6,
                                  fontSize: 10,
                                  color: '#ef4444',
                                  fontWeight: 600,
                                }}>
                                  超48h
                                </span>
                              )}
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
