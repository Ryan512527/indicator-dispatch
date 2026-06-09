import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { FiveCategoryWithdrawalSummary, FiveCategoryWithdrawalDetailRecord } from '../types'

const DISPLAY_FIELDS = [
  { key: 'district', label: '所属区县', width: '80px' },
  { key: 'is_recovered', label: '是否回捞', width: '90px' },
  { key: 'account', label: '宽带账号', width: '130px' },
  { key: 'global_access', label: '全球通标识', width: '100px' },
  { key: 'service_type', label: '服务类型', width: '120px' },
  { key: 'construction_address', label: '施工地址', width: '300px' },
  { key: 'accept_department', label: '受理部门', width: '120px' },
  { key: 'accept_time', label: '受理时间', width: '150px' },
  { key: 'to_install_time', label: '到装维时间', width: '150px' },
  { key: 'deadline', label: '完成时限', width: '150px' },
  { key: 'natural_duration', label: '处理时长（自然时）', width: '130px' },
  { key: 'return_time', label: '回单时间', width: '150px' },
  { key: 'archive_time', label: '归档时间', width: '150px' },
  { key: 'suspected_timeout', label: '疑似超时退单', width: '110px' },
  { key: 'return_note', label: '回单备注信息', width: '200px' },
  { key: 'specific_reason', label: '具体原因', width: '200px' },
]

export function FiveCategoryWithdrawalDetail({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<FiveCategoryWithdrawalDetailRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<FiveCategoryWithdrawalSummary>({
    district: '', day_withdrawal_total: '', day_reinstall_total: '',
    month_withdrawal_total: '', month_reinstall_total: '', report_date: '',
    latest_filename: '',
  })
  const [recoveredFilter, setRecoveredFilter] = useState<string>('all') // 'all' | '是' | '否'
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getFiveCategoryWithdrawalSummary(),
      api.getFiveCategoryWithdrawalDetails(page, pageSize),
    ])
      .then(([summaryData, detailData]) => {
        setSummary(summaryData as FiveCategoryWithdrawalSummary)
        setRecords(detailData.records as unknown as FiveCategoryWithdrawalDetailRecord[])
        setTotal(detailData.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

  // 是否回捞筛选
  const filteredRecords = records.filter(r => {
    if (recoveredFilter === 'all') return true
    const val = (r.is_recovered || '').trim()
    if (recoveredFilter === '是') return val === '是'
    if (recoveredFilter === '否') return val !== '是'
    return true
  })

  // 统计（基于当前页数据）
  const recoveredYesCount = records.filter(r => (r.is_recovered || '').trim() === '是').length
  const recoveredNoCount = records.filter(r => (r.is_recovered || '').trim() !== '是').length

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
            五类工单退撤单明细
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
            <div style={{ fontSize: 11, color: '#888' }}>日退撤总量</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>
              {summary.day_withdrawal_total || '—'}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>日重装量</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#166534' }}>
              {summary.day_reinstall_total || '—'}
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

      {/* 是否回捞筛选 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, padding: '0 4px' }}>
        {(['all', '是', '否'] as const).map(val => {
          const isActive = recoveredFilter === val
          const label = val === 'all' ? '全部' : val === '是' ? '✅ 已回捞' : '❌ 未回捞'
          const count = val === 'all' ? total : val === '是' ? recoveredYesCount : recoveredNoCount
          const badge = val === '是'
            ? { bg: '#f0fdf4', color: '#16a34a', border: '#86efac' }
            : val === '否'
            ? { bg: '#fef2f2', color: '#dc2626', border: '#fca5a5' }
            : { bg: '#f8fafc', color: '#64748b', border: '#cbd5e1' }
          return (
            <button
              key={val}
              onClick={() => setRecoveredFilter(val)}
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
          {filteredRecords.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
              {records.length === 0 ? '暂无退撤单数据' : '没有匹配筛选条件的记录'}
            </div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 13,
                  minWidth: 2200,
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
                    {filteredRecords.map((rec, idx) => (
                      <tr
                        key={rec.id}
                        style={{
                          background: idx % 2 === 0 ? '#fff' : '#fafafa',
                          borderBottom: '1px solid #f0f0f0',
                        }}
                      >
                        {DISPLAY_FIELDS.map(f => {
                          const val = (rec as unknown as Record<string, string>)[f.key] || ''
                          // 疑似超时退单高亮：值为"是"时显示红色
                          const isTimeout = f.key === 'suspected_timeout'
                          const isTimeoutYes = isTimeout && val === '是'
                          // 是否回捞高亮
                          const isRecovered = f.key === 'is_recovered'
                          const isRecoveredYes = isRecovered && val === '是'
                          return (
                            <td key={f.key} style={{
                              padding: '8px 12px',
                              color: isTimeoutYes ? '#ef4444' : isRecoveredYes ? '#16a34a' : '#333',
                              fontWeight: (isTimeoutYes || isRecoveredYes) ? 600 : 400,
                              maxWidth: f.width,
                              whiteSpace: 'normal',
                              wordBreak: 'break-all',
                              lineHeight: 1.5,
                            }}>
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
