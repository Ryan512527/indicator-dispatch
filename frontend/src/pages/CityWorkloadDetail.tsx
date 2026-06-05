import { useState, useEffect } from 'react'
import { api } from '../services/api'
import type { CityWorkloadWorker, CityWorkloadSummary } from '../types'

// 工作类型显示顺序（与图片一致）
const WORK_TYPES = ['装移拆', '投诉', 'LAN口', '巡检', '一户一案', '质差弱光']

function WorkerCard({ worker }: { worker: CityWorkloadWorker }) {
  const firstChar = worker.worker_name ? worker.worker_name.charAt(0) : '?'
  const workload = worker.workload || {}

  // 获取某个工作类型的积压和当日值
  const getVal = (type: string) => {
    const w = workload[type]
    if (!w) return { backlog: 0, today: 0 }
    return { backlog: w.backlog || 0, today: w.today || 0 }
  }

  // 积压值的颜色标签
  const getBacklogColor = (val: number) => {
    if (val >= 50) return { bg: '#fee2e2', text: '#dc2626' }
    if (val >= 20) return { bg: '#ffedd5', text: '#ea580c' }
    if (val >= 10) return { bg: '#fef3c7', text: '#d97706' }
    if (val > 0) return { bg: '#ecfdf5', text: '#059669' }
    return { bg: '#f3f4f6', text: '#9ca3af' }
  }

  return (
    <div style={{
      background: '#fffbeb',
      borderRadius: 12,
      padding: '16px 18px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      border: '1px solid #fde68a',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      {/* 头部：头像 + 姓名 + 区域 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
        <div style={{
          width: 40,
          height: 40,
          borderRadius: '50%',
          background: '#f59e0b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 16,
          fontWeight: 600,
          flexShrink: 0,
        }}>
          {firstChar}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a2e', lineHeight: 1.3 }}>
            {worker.worker_name}
          </div>
          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
            {worker.grid || worker.area || '—'}
          </div>
        </div>
      </div>

      {/* 表头 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 60px 60px',
        gap: 8,
        fontSize: 11,
        color: '#9ca3af',
        paddingBottom: 6,
        borderBottom: '1px solid #fde68a',
      }}>
        <div></div>
        <div style={{ textAlign: 'center' }}>积压</div>
        <div style={{ textAlign: 'center' }}>当日</div>
      </div>

      {/* 工作类型数据行 */}
      {WORK_TYPES.map(type => {
        const { backlog, today } = getVal(type)
        const color = getBacklogColor(backlog)
        return (
          <div key={type} style={{
            display: 'grid',
            gridTemplateColumns: '1fr 60px 60px',
            gap: 8,
            alignItems: 'center',
            fontSize: 13,
          }}>
            <div style={{ color: '#4b5563' }}>{type}</div>
            <div style={{ textAlign: 'center' }}>
              {backlog > 0 ? (
                <span style={{
                  display: 'inline-block',
                  padding: '2px 8px',
                  borderRadius: 6,
                  background: color.bg,
                  color: color.text,
                  fontSize: 12,
                  fontWeight: 600,
                  minWidth: 28,
                }}>
                  {backlog}
                </span>
              ) : (
                <span style={{ color: '#d1d5db', fontSize: 12 }}>0</span>
              )}
            </div>
            <div style={{ textAlign: 'center', color: today > 0 ? '#4b5563' : '#d1d5db', fontSize: 12 }}>
              {today}
            </div>
          </div>
        )
      })}

      {/* 小计行 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 60px 60px',
        gap: 8,
        alignItems: 'center',
        paddingTop: 8,
        borderTop: '1px dashed #fde68a',
        marginTop: 2,
      }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>小计</div>
        <div style={{ textAlign: 'center' }}>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 6,
            background: '#fee2e2',
            color: '#dc2626',
            fontSize: 13,
            fontWeight: 700,
            minWidth: 32,
          }}>
            {worker.total_backlog}
          </span>
        </div>
        <div style={{ textAlign: 'center', color: worker.total_today > 0 ? '#374151' : '#d1d5db', fontSize: 13, fontWeight: 600 }}>
          {worker.total_today}
        </div>
      </div>
    </div>
  )
}

export function CityWorkloadDetail({ onBack }: { onBack: () => void }) {
  const [workers, setWorkers] = useState<CityWorkloadWorker[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<CityWorkloadSummary | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getCityWorkloadSummary(),
      api.getCityWorkloadWorkers(),
    ])
      .then(([summaryData, workersData]) => {
        setSummary(summaryData as CityWorkloadSummary)
        setWorkers((workersData as { workers: CityWorkloadWorker[] }).workers)
        setTotal((workersData as { total: number }).total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // 计算总积压和总当日
  const totalBacklog = workers.reduce((sum, w) => sum + (w.total_backlog || 0), 0)
  const totalToday = workers.reduce((sum, w) => sum + (w.total_today || 0), 0)

  // 计算各工作类型的积压总和
  const typeBacklogTotals: Record<string, number> = {}
  for (const type of WORK_TYPES) {
    typeBacklogTotals[type] = workers.reduce((sum, w) => {
      const wt = (w.workload || {})[type]
      return sum + (wt ? (wt.backlog || 0) : 0)
    }, 0)
  }
  // 当日总和
  const typeTodayTotals: Record<string, number> = {}
  for (const type of WORK_TYPES) {
    typeTodayTotals[type] = workers.reduce((sum, w) => {
      const wt = (w.workload || {})[type]
      return sum + (wt ? (wt.today || 0) : 0)
    }, 0)
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
            装维人员工作量明细
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
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>装维人员</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#1e40af' }}>
              {summary?.total_staff || '—'}
            </div>
          </div>

          {/* 工作类型积压分解 */}
          <div style={{ flex: 1, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', minWidth: 0 }}>
            <div style={{ fontSize: 11, color: '#888', marginRight: 2 }}>积压</div>
            {WORK_TYPES.map(type => (
              <div key={type} style={{
                textAlign: 'center',
                background: typeBacklogTotals[type] > 0 ? '#fef2f2' : '#f9fafb',
                borderRadius: 6,
                padding: '4px 10px',
              }}>
                <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 1 }}>{type}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: typeBacklogTotals[type] > 0 ? '#dc2626' : '#bbb' }}>
                  {typeBacklogTotals[type]}
                </div>
              </div>
            ))}
            <div style={{
              textAlign: 'center',
              background: '#fee2e2',
              borderRadius: 6,
              padding: '4px 10px',
              borderLeft: '2px solid #dc2626',
            }}>
              <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 1 }}>合计</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#dc2626' }}>
                {totalBacklog}
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>总当日</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#16a34a' }}>
              {totalToday}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#888' }}>统计日期</div>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#666' }}>
              {summary?.report_date || '—'}
            </div>
          </div>
        </div>
      </div>

      {/* 卡片网格 */}
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
        <div>
          {workers.length === 0 ? (
            <div style={{
              background: '#fff',
              borderRadius: 10,
              padding: 40,
              textAlign: 'center',
              color: '#999',
              boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}>
              暂无装维人员工作量数据
            </div>
          ) : (
            <>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                gap: 16,
              }}>
                {workers.map(worker => (
                  <WorkerCard key={worker.id} worker={worker} />
                ))}
              </div>
              <div style={{
                marginTop: 20,
                padding: '12px 16px',
                background: '#fff',
                borderRadius: 10,
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: 13,
                color: '#666',
                flexWrap: 'wrap',
                gap: 8,
              }}>
                <span>共 {total} 位装维人员</span>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  {WORK_TYPES.map(type => (
                    <span key={type}>
                      {type}: <strong style={{ color: typeBacklogTotals[type] > 0 ? '#dc2626' : '#bbb' }}>{typeBacklogTotals[type]}</strong>
                    </span>
                  ))}
                  <span>当日: <strong style={{ color: totalToday > 0 ? '#16a34a' : '#bbb' }}>{totalToday}</strong></span>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
