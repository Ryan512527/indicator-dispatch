import { useState, useEffect } from 'react'
import { api } from '../services/api'

// 6个展示字段（中文原名）
const DISPLAY_FIELDS = [
  '接入层断纤链路',
  '告警码名称',
  '发生时间',
  '具体原因',
  '是否影响业务',
  '故障历时',
]

export function AccessLayerFaultDetail({ onBack }: { onBack: () => void }) {
  const [records, setRecords] = useState<Record<string, string>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    api.getAccessLayerFaultDetail(page, pageSize)
      .then((detailData) => {
        setRecords(detailData.records as Record<string, string>[])
        setTotal(detailData.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  const totalPages = Math.ceil(total / pageSize)

  if (loading) {
    return <div style={{ padding: 32, textAlign: 'center', color: '#999' }}>加载中...</div>
  }

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
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>接入层通报</h2>
        <span style={{ fontSize: 13, color: total > 0 ? '#ef4444' : '#22c55e', fontWeight: 500 }}>
          横山区 &middot; {total > 0 ? `共 ${total} 条故障记录` : '当前无接入层故障'}
        </span>
      </div>

      {/* 详细数据表格 */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '20px 24px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}
      >
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: '#1a1a2e' }}>
          接入层故障详细数据
        </h3>

        {records.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <div style={{ fontSize: 16, color: '#22c55e', fontWeight: 600 }}>当前无接入层故障</div>
            <div style={{ fontSize: 13, color: '#999', marginTop: 8 }}>横山区最新报表无接入层断纤告警</div>
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
                    {DISPLAY_FIELDS.map((field) => (
                      <th
                        key={field}
                        style={{
                          padding: '8px 10px',
                          textAlign: 'left',
                          fontWeight: 600,
                          color: '#666',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {field}
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
                      来源文件
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec, idx) => (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid #f0f0f0',
                        background: idx % 2 === 0 ? '#fff' : '#fafafa',
                      }}
                    >
                      <td style={{ padding: '6px 10px', color: '#aaa' }}>
                        {(page - 1) * pageSize + idx + 1}
                      </td>
                      {DISPLAY_FIELDS.map((field) => {
                          const isLongField = field === '接入层断纤链路'
                          return (
                        <td
                          key={field}
                          style={{
                            padding: '6px 10px',
                            whiteSpace: isLongField ? 'normal' : 'nowrap',
                            wordBreak: isLongField ? 'break-all' : undefined,
                            maxWidth: isLongField ? 400 : 160,
                            overflow: isLongField ? 'visible' : 'hidden',
                            textOverflow: isLongField ? undefined : 'ellipsis',
                          }}
                          title={rec[field] || ''}
                        >
                          {field === '是否影响业务'
                            ? rec[field] === '是'
                              ? <span style={{ color: '#ef4444', fontWeight: 600 }}>是</span>
                              : rec[field] === '否'
                                ? <span style={{ color: '#22c55e' }}>否</span>
                                : rec[field] || '—'
                            : rec[field] || '—'}
                        </td>
                          )
                        })}
                      <td
                        style={{
                          padding: '6px 10px',
                          color: '#aaa',
                          fontSize: 12,
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={rec._source_file || ''}
                      >
                        {rec._source_file || ''}
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
