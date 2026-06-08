import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { EnterpriseBroadbandLowLightRecord } from '../types'

const DISPLAY_FIELDS: { key: keyof EnterpriseBroadbandLowLightRecord; label: string }[] = [
  { key: 'district', label: '区县' },
  { key: 'date', label: '日期' },
  { key: 'olt_name', label: 'OLT名称' },
  { key: 'olt_ip', label: 'OLT-IP' },
  { key: 'pon_port', label: 'PON口' },
  { key: 'onu_id', label: 'ONU-ID' },
  { key: 'rx_power_dbm', label: '收光dbm' },
  { key: 'community', label: '小区' },
  { key: 'account_bandwidth', label: '账号-带宽' },
]

export function EnterpriseBroadbandLowLightDetail({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<EnterpriseBroadbandLowLightRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    api.getEnterpriseBroadbandLowLightDetails({ page, page_size: pageSize })
      .then((data) => {
        setRecords(data.records as EnterpriseBroadbandLowLightRecord[])
        setTotal(data.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div>
      {/* 顶栏 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={onBack}
          style={{
            padding: '6px 14px',
            borderRadius: 6,
            border: '1px solid #ddd',
            background: '#fff',
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          &larr; 返回
        </button>
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>企宽弱光清单</h2>
        <span style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>
          横山区 &middot; 共 {total} 条
        </span>
      </div>

      {/* 数据表格 */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '20px 24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}
      >
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中...</div>
        ) : records.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
            <div style={{ fontSize: 16, color: '#999' }}>暂无数据</div>
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 13,
                  minWidth: 1000,
                }}
              >
                <thead>
                  <tr style={{ borderBottom: '2px solid #eee' }}>
                    <th
                      style={{
                        padding: '8px 10px',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: '#666',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      #
                    </th>
                    {DISPLAY_FIELDS.map((f) => (
                      <th
                        key={f.key}
                        style={{
                          padding: '8px 10px',
                          textAlign: 'left',
                          fontWeight: 600,
                          color: '#666',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {f.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec, idx) => (
                    <tr
                      key={rec.id || idx}
                      style={{
                        borderBottom: '1px solid #f0f0f0',
                        background: idx % 2 === 0 ? '#fff' : '#fafafa',
                      }}
                    >
                      <td style={{ padding: '6px 10px', color: '#aaa' }}>
                        {(page - 1) * pageSize + idx + 1}
                      </td>
                      {DISPLAY_FIELDS.map((f) => (
                        <td
                          key={f.key}
                          style={{
                            padding: '6px 10px',
                            whiteSpace: 'nowrap',
                            maxWidth: 200,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={String(rec[f.key] ?? '')}
                        >
                          {rec[f.key] || '—'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 分页 */}
            {totalPages > 1 && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  gap: 8,
                  marginTop: 16,
                  alignItems: 'center',
                }}
              >
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: '1px solid #ddd',
                    background: '#fff',
                    cursor: page <= 1 ? 'not-allowed' : 'pointer',
                    fontSize: 13,
                  }}
                >
                  上一页
                </button>
                <span style={{ fontSize: 13, color: '#666' }}>
                  {page} / {totalPages}（共 {total} 条）
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: '1px solid #ddd',
                    background: '#fff',
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
    </div>
  )
}
