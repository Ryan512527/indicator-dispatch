import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { DailyReportBacklogRecord } from '../types'

function fmtDisplay(iso: string) {
  if (!iso) return '—'
  return iso.replace('T', ' ').substring(0, 19)
}

function getWarningStyle(label: string) {
  if (label === '超48h') {
    return { background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' }
  }
  if (label === '超24h') {
    return { background: '#fff7ed', color: '#ea580c', border: '1px solid #fed7aa' }
  }
  if (label === '超8h') {
    return { background: '#fefce8', color: '#ca8a04', border: '1px solid #fef08a' }
  }
  return { background: '#f0fdf4', color: '#16a34a', border: '1px solid #bbf7d0' }
}

function getSourceBadge(source: string) {
  if (source === 'FTTR积压') {
    return { background: '#fdf2f8', color: '#be185d', label: 'FTTR' }
  }
  return { background: '#eff6ff', color: '#2563eb', label: '宽带' }
}

export function DailyReportDetail({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<DailyReportBacklogRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState<string>('all') // 'all' | '宽带积压' | 'FTTR积压'
  const pageSize = 50

  useEffect(() => {
    loadData()
  }, [page])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await api.getDailyReportBacklog(page, pageSize) as {
        records: DailyReportBacklogRecord[];
        total: number;
        page: number;
        page_size: number;
      }
      setRecords(data.records || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  // 前端搜索过滤（按宽带账号/施工地址/施工人姓名）+ 来源筛选
  const filteredRecords = records.filter(r => {
    // 来源筛选
    if (sourceFilter !== 'all' && r['数据来源'] !== sourceFilter) return false
    // 搜索过滤
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      (r['宽带账号'] || '').toLowerCase().includes(q) ||
      (r['施工地址'] || '').toLowerCase().includes(q) ||
      (r['施工人姓名'] || '').toLowerCase().includes(q) ||
      (r['用户品牌'] || '').toLowerCase().includes(q)
    )
  })

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // 统计
  const over48h = records.filter(r => r['时长提醒'] === '超48h').length
  const over24h = records.filter(r => r['时长提醒'] === '超24h').length
  const over8h = records.filter(r => r['时长提醒'] === '超8h').length
  const broadbandCount = records.filter(r => r['数据来源'] === '宽带积压').length
  const fttrCount = records.filter(r => r['数据来源'] === 'FTTR积压').length

  return (
    <div>
      {/* 顶部标题栏 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={onBack}
            style={{
              background: 'none',
              border: '1px solid #ddd',
              borderRadius: 6,
              padding: '6px 12px',
              cursor: 'pointer',
              fontSize: 14,
              color: '#666',
            }}
          >
            ← 返回看板
          </button>
          <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>
            日报 - 装机积压清单
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
        <span style={{ fontSize: 13, color: '#999', display: 'flex', gap: 16, alignItems: 'center' }}>
          <span>共 {total} 条</span>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            background: '#eff6ff',
            color: '#2563eb',
            fontSize: 12,
            fontWeight: 500,
          }}>
            宽带 {broadbandCount}
          </span>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 4,
            background: '#fdf2f8',
            color: '#be185d',
            fontSize: 12,
            fontWeight: 500,
          }}>
            FTTR {fttrCount}
          </span>
        </span>
      </div>

      {/* 积压时长概览 */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginBottom: 16,
        padding: '12px 20px',
        background: '#fff',
        borderRadius: 10,
        border: '1px solid #f0f0f0',
      }}>
        <div style={{ flex: 1, textAlign: 'center', borderRight: '1px solid #f0f0f0', paddingRight: 12 }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#dc2626' }}>{over48h}</div>
          <div style={{ fontSize: 12, color: '#dc2626' }}>超48小时</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', borderRight: '1px solid #f0f0f0', paddingRight: 12 }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#ea580c' }}>{over24h}</div>
          <div style={{ fontSize: 12, color: '#ea580c' }}>超24小时</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center', borderRight: '1px solid #f0f0f0', paddingRight: 12 }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#ca8a04' }}>{over8h}</div>
          <div style={{ fontSize: 12, color: '#ca8a04' }}>超8小时</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#16a34a' }}>{total - over48h - over24h - over8h}</div>
          <div style={{ fontSize: 12, color: '#16a34a' }}>正常</div>
        </div>
      </div>

      {/* 搜索栏 */}
      <div style={{ marginBottom: 12 }}>
        <input
          type="text"
          placeholder="搜索宽带账号、施工地址、施工人姓名、用户品牌..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          style={{
            width: '100%',
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid #e5e7eb',
            fontSize: 14,
            outline: 'none',
            background: '#fff',
          }}
        />
      </div>

      {/* 来源筛选 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {(['all', '宽带积压', 'FTTR积压'] as const).map(src => {
          const isActive = sourceFilter === src
          const label = src === 'all' ? '全部来源' : src === '宽带积压' ? '📡 宽带积压' : '📶 FTTR积压'
          const count = src === 'all' ? total : src === '宽带积压' ? broadbandCount : fttrCount
          const badge = src === 'FTTR积压'
            ? { bg: '#fdf2f8', color: '#be185d', border: '#f9a8d4' }
            : src === '宽带积压'
            ? { bg: '#eff6ff', color: '#2563eb', border: '#93c5fd' }
            : { bg: '#f8fafc', color: '#64748b', border: '#cbd5e1' }
          return (
            <button
              key={src}
              onClick={() => setSourceFilter(src)}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: `1.5px solid ${isActive ? badge.border : '#e5e7eb'}`,
                background: isActive ? badge.bg : '#fff',
                color: badge.color,
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {label} ({count})
            </button>
          )
        })}
      </div>

      {/* 数据表格 */}
      <div style={{
        background: '#fff',
        borderRadius: 10,
        border: '1px solid #f0f0f0',
        overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中...</div>
        ) : filteredRecords.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
            {searchQuery ? '未找到匹配记录' : '暂无积压数据'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 13,
              minWidth: 1400,
            }}>
              <thead>
                <tr style={{ background: '#fafafa', borderBottom: '2px solid #e5e7eb' }}>
                  {[
                    '所属区县', '宽带账号', '服务', '施工地址', '施工人姓名',
                    '工单状态', '受理时间', '到装维时间', '完成时限',
                    '装机历时(h)', '时长提醒', '用户品牌', '数据来源',
                  ].map(col => (
                    <th key={col} style={{
                      padding: '10px 8px',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: '#374151',
                      whiteSpace: 'nowrap',
                      fontSize: 12,
                      borderBottom: '2px solid #e5e7eb',
                    }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRecords.map((row, idx) => {
                  const warningStyle = getWarningStyle(row['时长提醒'] || '')
                  return (
                    <tr
                      key={row.id || idx}
                      style={{
                        background: idx % 2 === 0 ? '#fff' : '#fafafa',
                        borderBottom: '1px solid #f3f4f6',
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLTableRowElement).style.background = '#f0f7ff'
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLTableRowElement).style.background = idx % 2 === 0 ? '#fff' : '#fafafa'
                      }}
                    >
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#6b7280', fontSize: 12 }}>{row['所属区县'] || '—'}</td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#111827', fontWeight: 500, fontSize: 12 }}>{row['宽带账号'] || '—'}</td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#374151', fontSize: 12 }}>{row['服务'] || '—'}</td>
                      <td style={{ padding: '8px', color: '#374151', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }} title={row['施工地址']}>
                        {row['施工地址'] || '—'}
                      </td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#374151', fontSize: 12 }}>{row['施工人姓名'] || '—'}</td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', fontSize: 12 }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 4,
                          fontSize: 11,
                          background: row['工单状态'] === '已完成' ? '#f0fdf4' : '#fefce8',
                          color: row['工单状态'] === '已完成' ? '#16a34a' : '#ca8a04',
                          fontWeight: 500,
                        }}>
                          {row['工单状态'] || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#6b7280', fontSize: 12 }}>{fmtDisplay(row['受理时间'])}</td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#6b7280', fontSize: 12 }}>{fmtDisplay(row['到装维时间'])}</td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#6b7280', fontSize: 12 }}>{fmtDisplay(row['完成时限'])}</td>
                      <td style={{ padding: '8px', textAlign: 'center', fontWeight: 600, fontSize: 13, color: row['时长提醒'] ? '#dc2626' : '#374151' }}>
                        {row['装机历时(h)'] || '—'}
                      </td>
                      <td style={{ padding: '8px', textAlign: 'center' }}>
                        {row['时长提醒'] ? (
                          <span style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontSize: 11,
                            fontWeight: 600,
                            ...warningStyle,
                          }}>
                            {row['时长提醒']}
                          </span>
                        ) : (
                          <span style={{ fontSize: 12, color: '#9ca3af' }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', color: '#374151', fontSize: 12 }}>{row['用户品牌'] || '—'}</td>
                      <td style={{ padding: '8px', textAlign: 'center' }}>
                        {(() => {
                          const sb = getSourceBadge(row['数据来源'] || '')
                          return (
                            <span style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 600,
                              background: sb.background,
                              color: sb.color,
                            }}>
                              {sb.label}
                            </span>
                          )
                        })()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 分页 */}
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 8,
        padding: '16px 0',
      }}>
        <button
          disabled={page <= 1}
          onClick={() => setPage(p => Math.max(1, p - 1))}
          style={{
            padding: '6px 14px',
            border: '1px solid #ddd',
            borderRadius: 6,
            background: page <= 1 ? '#f9fafb' : '#fff',
            color: page <= 1 ? '#ccc' : '#374151',
            cursor: page <= 1 ? 'default' : 'pointer',
            fontSize: 13,
          }}
        >
          上一页
        </button>
        <span style={{ fontSize: 13, color: '#666' }}>
          第 {page} / {totalPages} 页
        </span>
        <button
          disabled={page >= totalPages}
          onClick={() => setPage(p => Math.min(totalPages, p + 1))}
          style={{
            padding: '6px 14px',
            border: '1px solid #ddd',
            borderRadius: 6,
            background: page >= totalPages ? '#f9fafb' : '#fff',
            color: page >= totalPages ? '#ccc' : '#374151',
            cursor: page >= totalPages ? 'default' : 'pointer',
            fontSize: 13,
          }}
        >
          下一页
        </button>
      </div>
    </div>
  )
}
