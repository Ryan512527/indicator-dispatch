import { useState, useEffect } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { api } from '../services/api'
import type { WirelessOutageTrend } from '../types'

echarts.use([LineChart, GridComponent, TooltipComponent, TitleComponent, CanvasRenderer])

// 9个展示字段（中文原名）
const DISPLAY_FIELDS = [
  '基站类型',
  '站址名称',
  '告警名称',
  '告警时间',
  '退服时长(h)',
  '保障场景',
  '是否超时',
  '是否塔维',
  '机房名称',
]

function fmtTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function WirelessOutageDetail({ onBack }: { onBack: () => void }) {
  const [trend, setTrend] = useState<WirelessOutageTrend[]>([])
  const [records, setRecords] = useState<Record<string, string>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getWirelessOutageTrend(48),
      api.getWirelessOutageDetail(page, pageSize),
    ])
      .then(([trendData, detailData]) => {
        setTrend(trendData as WirelessOutageTrend[])
        setRecords(detailData.records as Record<string, string>[])
        setTotal(detailData.total || 0)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [page])

  // 48小时趋势图配置
  const chartOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const p = params[0]
        return `${fmtTime(p.axisValue)}<br/>退服数量: <b>${p.value}</b>`
      },
    },
    grid: {
      left: 50,
      right: 20,
      top: 20,
      bottom: 40,
    },
    xAxis: {
      type: 'category' as const,
      data: trend.map(t => t.hour),
      axisLabel: {
        formatter: (val: string) => fmtTime(val),
        rotate: 45,
        fontSize: 11,
      },
    },
    yAxis: {
      type: 'value' as const,
      name: '退服数量',
      minInterval: 1,
    },
    series: [
      {
        type: 'line',
        data: trend.map(t => t.count),
        smooth: true,
        lineStyle: { color: '#ef4444', width: 2 },
        itemStyle: { color: '#ef4444' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(239,68,68,0.25)' },
            { offset: 1, color: 'rgba(239,68,68,0.02)' },
          ]),
        },
        symbol: 'circle',
        symbolSize: 6,
      },
    ],
  }

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
        <h2 style={{ fontSize: 22, fontWeight: 600, margin: 0 }}>无线退服清单</h2>
        <span style={{ fontSize: 13, color: total > 0 ? '#ef4444' : '#22c55e', fontWeight: 500 }}>
          横山区 &middot; {total > 0 ? `共 ${total} 条退服记录` : '当前无退服基站'}
        </span>
      </div>

      {/* 48小时趋势图 */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '20px 24px 8px',
          marginBottom: 24,
          boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}
      >
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: '#1a1a2e' }}>
          最近 48 小时退服数量趋势
        </h3>
        {trend.length > 0 ? (
          <ReactEChartsCore
            echarts={echarts}
            option={chartOption}
            style={{ height: 300 }}
            notMerge
          />
        ) : (
          <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ccc' }}>
            暂无趋势数据
          </div>
        )}
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
          退服详细数据
        </h3>

        {records.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
            <div style={{ fontSize: 16, color: '#22c55e', fontWeight: 600 }}>当前无退服基站</div>
            <div style={{ fontSize: 13, color: '#999', marginTop: 8 }}>横山区最新报表示无退服告警</div>
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
                      {DISPLAY_FIELDS.map((field) => (
                        <td
                          key={field}
                          style={{
                            padding: '6px 10px',
                            whiteSpace: 'nowrap',
                            maxWidth: 160,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={rec[field] || ''}
                        >
                          {field === '是否超时'
                            ? rec[field] === '是'
                              ? <span style={{ color: '#ef4444', fontWeight: 600 }}>是</span>
                              : rec[field] || '—'
                            : rec[field] || '—'}
                        </td>
                      ))}
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
