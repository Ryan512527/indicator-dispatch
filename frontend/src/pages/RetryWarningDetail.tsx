import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { RetryWarningDetailRecord, CustomerRepairDetailRecord } from '../types'

const RETRY_FIELDS = [
  { key: 'district',         label: '所属区县',   width: '7%' },
  { key: 'retry_count',      label: '重投',       width: '5%' },
  { key: 'broadband_account', label: '宽带帐号',   width: '11%' },
  { key: 'is_global_user',    label: '是否全球通', width: '8%' },
  { key: 'customer_contact',  label: '客户联系方式', width: '11%' },
  { key: 'construction_address', label: '施工地址',   width: '32%' },
  { key: 'days_elapsed',     label: '历时天数',   width: '8%' },
  { key: 'handler_name',     label: '处理人姓名', width: '8%' },
  { key: 'complaint_content', label: '投诉内容',   width: '10%' },
]

const REPAIR_FIELDS = [
  { key: 'district',      label: '县区',     width: '7%' },
  { key: 'repair_count',  label: '催修次数', width: '8%' },
  { key: 'account',       label: '账号',     width: '12%' },
  { key: 'call_number',   label: '来电号码', width: '12%' },
  { key: 'address',       label: '地址',     width: '45%' },
  { key: 'register_date', label: '登记日期', width: '16%' },
]

function DetailTable<T extends { id: number }>({
  title, records, total, loading, fields, page, pageSize, onPageChange,
}: {
  title: string
  records: T[]
  total: number
  loading: boolean
  fields: { key: string; label: string; width: string }[]
  page: number
  pageSize: number
  onPageChange: (p: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div style={{ background: '#fff', borderRadius: 12, padding: '16px 20px', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}>
      <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e', marginBottom: 12 }}>
        {title}
        <span style={{ fontSize: 12, color: '#999', fontWeight: 400, marginLeft: 8 }}>
          共 {total} 条
        </span>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>加载中...</div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: fields.map(f => f.width).join(' '), background: '#f5f5f5', padding: '6px 0', fontWeight: 600, fontSize: 12, color: '#666' }}>
              {fields.map(f => (
                <div key={f.key} style={{ padding: '0 6px', textAlign: 'center' }}>{f.label}</div>
              ))}
            </div>
            {records.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>暂无数据</div>
            ) : (
              records.map((row, ri) => (
                <div key={row.id} style={{
                  display: 'grid', gridTemplateColumns: fields.map(f => f.width).join(' '),
                  padding: '7px 0', borderBottom: '1px solid #f0f0f0',
                  background: ri % 2 === 0 ? '#fff' : '#fafafa',
                  fontSize: 12, color: '#333',
                }}>
                  {fields.map(f => (
                    <div key={f.key} title={String((row as any)[f.key] ?? '')} style={{
                      padding: '0 6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'center',
                    }}>
                      {(row as any)[f.key] ?? '—'}
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>

          {/* 分页 */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 12, fontSize: 13 }}>
            <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}
              style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid #d9d9d9', background: page <= 1 ? '#f5f5f5' : '#fff', cursor: page <= 1 ? 'not-allowed' : 'pointer' }}>
              上一页
            </button>
            <span style={{ color: '#666' }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}
              style={{ padding: '4px 12px', borderRadius: 6, border: '1px solid #d9d9d9', background: page >= totalPages ? '#f5f5f5' : '#fff', cursor: page >= totalPages ? 'not-allowed' : 'pointer' }}>
              下一页
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function RetryWarningDetailPage({ onNavigate }: { onNavigate: (p: { name: string }) => void }) {
  // 重投预警清单
  const [retryRecords, setRetryRecords] = useState<RetryWarningDetailRecord[]>([])
  const [retryTotal, setRetryTotal] = useState(0)
  const [retryPage, setRetryPage] = useState(1)
  const [retryLoading, setRetryLoading] = useState(true)

  // 客户催修清单
  const [repairRecords, setRepairRecords] = useState<CustomerRepairDetailRecord[]>([])
  const [repairTotal, setRepairTotal] = useState(0)
  const [repairPage, setRepairPage] = useState(1)
  const [repairLoading, setRepairLoading] = useState(true)

  const pageSize = 50

  // 加载重投预警明细
  useEffect(() => {
    setRetryLoading(true)
    ;(api as any).getRetryWarningDetails(retryPage, pageSize)
      .then((data: any) => {
        setRetryRecords(data.records as RetryWarningDetailRecord[])
        setRetryTotal(data.total as number)
      })
      .catch(console.error)
      .finally(() => setRetryLoading(false))
  }, [retryPage])

  // 加载客户催修明细
  useEffect(() => {
    setRepairLoading(true)
    ;(api as any).getCustomerRepairDetails(repairPage, pageSize)
      .then((data: any) => {
        setRepairRecords(data.records as CustomerRepairDetailRecord[])
        setRepairTotal(data.total as number)
      })
      .catch(console.error)
      .finally(() => setRepairLoading(false))
  }, [repairPage])

  return (
    <div style={{ padding: '20px 24px' }}>
      {/* 页面头部 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={() => onNavigate({ name: 'dashboard' })}
          style={{
            background: '#f5f5f5', border: 'none', borderRadius: 8,
            padding: '6px 14px', cursor: 'pointer', fontSize: 13, color: '#666',
          }}
        >
          ← 返回
        </button>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#1a1a2e' }}>
          重投预警工单梳理
        </div>
      </div>

      {/* 重投预警清单 */}
      <div style={{ marginBottom: 20 }}>
        <DetailTable
          title="重投预警清单"
          records={retryRecords}
          total={retryTotal}
          loading={retryLoading}
          fields={RETRY_FIELDS}
          page={retryPage}
          pageSize={pageSize}
          onPageChange={p => setRetryPage(p)}
        />
      </div>

      {/* 客户催修清单 */}
      <div>
        <DetailTable
          title="客户催修清单"
          records={repairRecords}
          total={repairTotal}
          loading={repairLoading}
          fields={REPAIR_FIELDS}
          page={repairPage}
          pageSize={pageSize}
          onPageChange={p => setRepairPage(p)}
        />
      </div>
    </div>
  )
}
