import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { ReportType, ReportRecord } from '../types'

export function ReportDetail({ reportTypeId }: { reportTypeId: number }) {
  const [rt, setRt] = useState<ReportType | null>(null)
  const [records, setRecords] = useState<ReportRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    loadData()
  }, [reportTypeId, page])

  async function loadData() {
    setLoading(true)
    try {
      const [typesRes, recsRes] = await Promise.all([
        api.listReportTypes(),
        api.getReportRecords(reportTypeId, page, pageSize),
      ])
      const found = (typesRes as ReportType[]).find((t: ReportType) => t.id === reportTypeId)
      setRt(found || null)
      setRecords(recsRes.records as ReportRecord[])
      setTotal(recsRes.total || 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  function goBack() {
    window.location.hash = '#/'
  }

  if (loading) return <div style={{ padding: 32, color: '#999' }}>加载中...</div>

  const columns = rt?.column_hint?.length
    ? rt.column_hint.slice(0, 10)
    : records.length > 0
      ? Object.keys(records[0]).filter(k => !k.startsWith('_'))
      : []

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, cursor: 'pointer', color: '#4f46e5' }} onClick={goBack}>
        ← 返回看板
      </div>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 4 }}>
        {rt?.name || `报表 #${reportTypeId}`}
      </h2>
      <div style={{ color: '#888', marginBottom: 16, fontSize: 13 }}>
        分类：{rt?.category || '未分类'} ｜ 总记录数：{total} ｜ 文件数：{rt?.file_count || 0}
      </div>

      {/* Records table */}
      {records.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>暂无数据</div>
      ) : (
        <div style={{ background: '#fff', borderRadius: 10, padding: 16, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #eee' }}>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#666' }}>#</th>
                {columns.map(col => (
                  <th key={col} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#666' }}>{col}</th>
                ))}
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#666' }}>来源文件</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}>
                  <td style={{ padding: '6px 10px', color: '#aaa' }}>{(page - 1) * pageSize + idx + 1}</td>
                  {columns.map(col => (
                    <td key={col} style={{ padding: '6px 10px' }}>{rec[col] || ''}</td>
                  ))}
                  <td style={{ padding: '6px 10px', color: '#aaa', fontSize: 12 }}>{rec._source_file || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #ddd', cursor: page <= 1 ? 'not-allowed' : 'pointer' }}>上一页</button>
              <span style={{ alignSelf: 'center', fontSize: 13 }}>{page} / {totalPages}（共 {total} 条）</span>
              <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid #ddd', cursor: page >= totalPages ? 'not-allowed' : 'pointer' }}>下一页</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
