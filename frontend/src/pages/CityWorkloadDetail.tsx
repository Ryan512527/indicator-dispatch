import { useState, useEffect, useMemo } from 'react'
import { api } from '../services/api'
import type { CityWorkloadWorker, CityWorkloadSummary } from '../types'

// 工作类型显示顺序
const WORK_TYPES = ['装移拆', '投诉', 'LAN口', '巡检', '一户一案', '质差弱光']

// 网格分组配色（循环使用）
const GRID_COLORS = [
  { border: '#3b82f6', bg: '#eff6ff', accent: '#1d4ed8', dot: '#3b82f6' },
  { border: '#8b5cf6', bg: '#f5f3ff', accent: '#6d28d9', dot: '#8b5cf6' },
  { border: '#06b6d4', bg: '#ecfeff', accent: '#0e7490', dot: '#06b6d4' },
  { border: '#f59e0b', bg: '#fffbeb', accent: '#b45309', dot: '#f59e0b' },
  { border: '#10b981', bg: '#ecfdf5', accent: '#047857', dot: '#10b981' },
  { border: '#ec4899', bg: '#fdf2f8', accent: '#be185d', dot: '#ec4899' },
]

// 积压颜色标签
function getBacklogColor(val: number) {
  if (val >= 50) return { bg: '#fee2e2', text: '#dc2626' }
  if (val >= 20) return { bg: '#ffedd5', text: '#ea580c' }
  if (val >= 10) return { bg: '#fef3c7', text: '#d97706' }
  if (val > 0) return { bg: '#ecfdf5', text: '#059669' }
  return { bg: '#f3f4f6', text: '#9ca3af' }
}

// ========== 人员卡片 ==========
function WorkerCard({ worker }: { worker: CityWorkloadWorker }) {
  const firstChar = worker.worker_name ? worker.worker_name.charAt(0) : '?'
  const workload = worker.workload || {}

  const getVal = (type: string) => {
    const w = workload[type]
    if (!w) return { backlog: 0, today: 0 }
    return { backlog: w.backlog || 0, today: w.today || 0 }
  }

  return (
    <div style={{
      background: '#fff',
      borderRadius: 10,
      padding: '14px 16px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
      border: '1px solid #f0f0f0',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      transition: 'box-shadow 0.2s',
    }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)')}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)')}
    >
      {/* 头部：头像 + 姓名 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 32,
          height: 32,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontSize: 13,
          fontWeight: 600,
          flexShrink: 0,
        }}>
          {firstChar}
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a2e' }}>
          {worker.worker_name}
        </div>
      </div>

      {/* 工作类型数据行 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {WORK_TYPES.map(type => {
          const { backlog, today } = getVal(type)
          const color = getBacklogColor(backlog)
          return (
            <div key={type} style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              padding: '2px 0',
            }}>
              <span style={{ color: '#9ca3af', minWidth: 52 }}>{type}</span>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                {backlog > 0 ? (
                  <span style={{
                    display: 'inline-block',
                    padding: '1px 6px',
                    borderRadius: 4,
                    background: color.bg,
                    color: color.text,
                    fontSize: 11,
                    fontWeight: 600,
                    minWidth: 20,
                    textAlign: 'center',
                  }}>
                    {backlog}
                  </span>
                ) : (
                  <span style={{ color: '#d1d5db', fontSize: 11, minWidth: 20, textAlign: 'center' }}>0</span>
                )}
                <span style={{ color: today > 0 ? '#6b7280' : '#d1d5db', fontSize: 11, minWidth: 14, textAlign: 'right' }}>
                  {today}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* 小计行 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingTop: 6,
        borderTop: '1px dashed #e5e7eb',
        marginTop: 2,
      }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>小计</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{
            display: 'inline-block',
            padding: '1px 8px',
            borderRadius: 4,
            background: '#fee2e2',
            color: '#dc2626',
            fontSize: 12,
            fontWeight: 700,
          }}>
            {worker.total_backlog}
          </span>
          <span style={{
            color: worker.total_today > 0 ? '#374151' : '#d1d5db',
            fontSize: 12,
            fontWeight: 600,
            minWidth: 14,
            textAlign: 'right',
          }}>
            {worker.total_today}
          </span>
        </div>
      </div>
    </div>
  )
}

// ========== 网格分组区块 ==========
function GridSection({
  gridName,
  workers,
  color,
  defaultCollapsed,
}: {
  gridName: string
  workers: CityWorkloadWorker[]
  color: (typeof GRID_COLORS)[number]
  defaultCollapsed: boolean
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  // 网格汇总
  const gridBacklog = workers.reduce((s, w) => s + (w.total_backlog || 0), 0)
  const gridToday = workers.reduce((s, w) => s + (w.total_today || 0), 0)

  return (
    <div style={{
      background: color.bg,
      borderRadius: 12,
      border: `1px solid ${color.border}30`,
      overflow: 'hidden',
    }}>
      {/* 网格头部 - 可点击折叠 */}
      <div
        onClick={() => setCollapsed(!collapsed)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 20px',
          cursor: 'pointer',
          userSelect: 'none',
          transition: 'background 0.15s',
          borderBottom: collapsed ? 'none' : `1px solid ${color.border}20`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* 折叠箭头 */}
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 20,
            height: 20,
            transition: 'transform 0.2s',
            transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
            fontSize: 12,
            color: color.accent,
          }}>
            ▼
          </span>
          {/* 色点 */}
          <span style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: color.dot,
            flexShrink: 0,
          }} />
          {/* 网格名 */}
          <span style={{
            fontSize: 15,
            fontWeight: 600,
            color: color.accent,
          }}>
            {gridName}
          </span>
          {/* 人数标签 */}
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 8,
            background: `${color.border}18`,
            color: color.accent,
            fontSize: 11,
            fontWeight: 500,
          }}>
            {workers.length}人
          </span>
        </div>

        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, color: '#888', marginBottom: 1 }}>总积压</div>
            <div style={{
              fontSize: 16,
              fontWeight: 700,
              color: gridBacklog > 0 ? '#dc2626' : '#bbb',
            }}>
              {gridBacklog}
            </div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 10, color: '#888', marginBottom: 1 }}>总当日</div>
            <div style={{
              fontSize: 16,
              fontWeight: 700,
              color: gridToday > 0 ? '#16a34a' : '#bbb',
            }}>
              {gridToday}
            </div>
          </div>
        </div>
      </div>

      {/* 人员卡片列表 */}
      {!collapsed && (
        <div style={{
          padding: '12px 20px 16px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 12,
        }}>
          {workers.map(worker => (
            <WorkerCard key={worker.id} worker={worker} />
          ))}
        </div>
      )}
    </div>
  )
}

// ========== 主页面 ==========
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

  // 按网格分组
  const gridGroups = useMemo(() => {
    const groups: { grid: string; workers: CityWorkloadWorker[] }[] = []
    const seen = new Map<string, CityWorkloadWorker[]>()

    for (const w of workers) {
      const grid = w.grid || '未知网格'
      if (!seen.has(grid)) {
        seen.set(grid, [])
        groups.push({ grid, workers: seen.get(grid)! })
      }
      seen.get(grid)!.push(w)
    }
    return groups
  }, [workers])

  // 全局汇总
  const totalBacklog = workers.reduce((sum, w) => sum + (w.total_backlog || 0), 0)
  const totalToday = workers.reduce((sum, w) => sum + (w.total_today || 0), 0)

  const typeBacklogTotals: Record<string, number> = {}
  for (const type of WORK_TYPES) {
    typeBacklogTotals[type] = workers.reduce((sum, w) => {
      const wt = (w.workload || {})[type]
      return sum + (wt ? (wt.backlog || 0) : 0)
    }, 0)
  }

  return (
    <div>
      {/* ===== 顶部标题栏 ===== */}
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

      {/* ===== 按网格分组的内容区 ===== */}
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
      ) : workers.length === 0 ? (
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {gridGroups.map((group, idx) => (
              <GridSection
                key={group.grid}
                gridName={group.grid}
                workers={group.workers}
                color={GRID_COLORS[idx % GRID_COLORS.length]}
                defaultCollapsed={false}
              />
            ))}
          </div>

          {/* 底部统计条 */}
          <div style={{
            marginTop: 20,
            padding: '12px 20px',
            background: '#fff',
            borderRadius: 10,
            boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: 13,
            color: '#666',
            flexWrap: 'wrap',
            gap: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>共 <strong>{gridGroups.length}</strong> 个网格，<strong>{total}</strong> 位装维人员</span>
            </div>
            <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              {WORK_TYPES.map(type => (
                <span key={type}>
                  {type}: <strong style={{ color: typeBacklogTotals[type] > 0 ? '#dc2626' : '#bbb' }}>{typeBacklogTotals[type]}</strong>
                </span>
              ))}
              <span style={{ borderLeft: '1px solid #e5e7eb', paddingLeft: 10 }}>
                当日: <strong style={{ color: totalToday > 0 ? '#16a34a' : '#bbb' }}>{totalToday}</strong>
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
