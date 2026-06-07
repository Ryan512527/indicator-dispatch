import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { OfflineDispatchDetailRecord } from '../types'

const DISPLAY_FIELDS: { key: keyof OfflineDispatchDetailRecord; label: string }[] = [
  { key: 'district', label: '所属区县' },
  { key: 'timeout_limit', label: '超时时限' },
  { key: 'broadband_account', label: '宽带帐号' },
  { key: 'is_vip_customer', label: '是否重要客户' },
  { key: 'customer_contact', label: '客户联系方式' },
  { key: 'construction_address', label: '施工地址' },
  { key: 'handler_name', label: '处理人姓名' },
]

type TabKey = 'all' | '在途' | '往月'

export function OfflineDispatchDetail({ onBack }: { onBack: () => void }) {
  const [activeTab, setActiveTab] = useState<TabKey>('all')
  const [records, setRecords] = useState<OfflineDispatchDetailRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    const params: { category?: string; page: number; page_size: number } = {
      page,
      page_size: pageSize,
    }
    if (activeTab !== 'all') {
      params.category = activeTab
    }
    api.getOfflineDispatchDetails(params)
      .then((data) => {
        setRecords(data.records as OfflineDispatchDetailRecord[])
        setTotal(data.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [activeTab, page])

  const totalPages = Math.ceil(total / pageSize)

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: '在途', label: '在途' },
    { key: '往月', label: '往月' },
  ]

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
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>线下派单投诉积压清单</h2>
        <span style={{ fontSize: 13, color: '#666', fontWeight: 500 }}>
          横山区 &middot; 共 {total} 条
        </span>
      </div>

      {/* 分类标签 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key)
              setPage(1)
            }}
            style={{
              padding: '6px 16px',
              borderRadius: 6,
              border: `1px solid ${activeTab === tab.key ? '#3b82f6' : '#ddd'}`,
              background: activeTab === tab.key ? '#3b82f6' : '#fff',
              color: activeTab === tab.key ? '#fff' : '#333',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            {tab.label}
          </button>
        ))}
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
                  minWidth: 900,
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
                    <th
                      style={{
                        padding: '8px 10px',
                        textAlign: 'left',
                        fontWeight: 600,
                        color: '#666',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      分类
                    </th>
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
                          {f.key === 'is_vip_customer'
                            ? rec[f.key] === '是'
                              ? <span style={{ color: '#f59e0b', fontWeight: 600 }}>是</span>
                              : rec[f.key] || '—'
                            : rec[f.key] || '—'}
                        </td>
                      ))}
                      <td>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 500,
                            background: rec.category === '往月' ? '#fef3c7' : '#dbeafe',
                            color: rec.category === '往月' ? '#92400e' : '#1e40af',
                          }}
                        >
                          {rec.category}
                        </span>
                      </td>
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
