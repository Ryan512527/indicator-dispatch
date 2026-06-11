import { useState, useRef, useEffect } from 'react'
import ReactEChartsCore from 'echarts-for-react'
import { api } from '../services/api'
import type { ChatResponse } from '../types'

interface Message {
  role: 'user' | 'assistant';
  content: string;
  data?: ChatResponse['data'];
  answer?: string;
}

export function AIChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '你好！我是指标调度系统的 AI 助手，已接入 OpenRouter 大模型。你可以问我：\n- "有哪些指标" 查看指标列表\n- "系统总览" 查看概况\n- "最高的指标" 查看排名\n- 或输入任意问题，我会智能回答',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  /** Build history from current messages (last 10 turns) for LLM context */
  function buildHistory(): Array<{ role: string; content: string }> {
    const recent = messages.slice(-10)
    return recent
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.answer || m.content,
      }))
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const history = buildHistory()
      const res = await api.aiChat(text, history)
      const content = renderContent(res)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content, data: res.data, answer: res.answer },
      ])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，查询出错了，请稍后重试。',
      }])
    } finally {
      setLoading(false)
    }
  }

  function renderContent(res: ChatResponse): string {
    if (res.intent === 'error') return 'Error: ' + JSON.stringify(res.data)

    // If LLM provided a natural language answer, show it
    if (res.answer) return res.answer

    const data = res.data
    if (data.type === 'text') return data.content || ''
    if (data.type === 'table') return `找到 ${data.rows?.length || 0} 条记录`
    if (data.type === 'bar') return data.title || '图表数据'
    return '查询完成'
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 48px)' }}>
      <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 16 }}>AI Data Chat</h2>

      <div ref={listRef} style={{
        flex: 1, overflowY: 'auto', marginBottom: 16,
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            maxWidth: '80%',
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              padding: '12px 16px',
              borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              background: msg.role === 'user' ? '#4f46e5' : '#fff',
              color: msg.role === 'user' ? '#fff' : '#333',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.6,
              fontSize: 14,
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            }}>
              {msg.content}
            </div>
            {msg.data?.type === 'bar' && msg.data.categories && msg.data.values && (
              <div style={{ background: '#fff', borderRadius: 10, marginTop: 8, padding: 12 }}>
                <ReactEChartsCore option={{
                  title: msg.data.title ? { text: msg.data.title, textStyle: { fontSize: 14 } } : undefined,
                  tooltip: {},
                  xAxis: { type: 'category', data: msg.data.categories, axisLabel: { rotate: 30 } },
                  yAxis: { type: 'value' },
                  series: [{ type: 'bar', data: msg.data.values, itemStyle: { color: '#4f46e5' } }],
                  grid: { left: 50, right: 20, bottom: 50, top: msg.data.title ? 40 : 10 },
                }} style={{ height: 250 }} />
              </div>
            )}
            {msg.data?.type === 'table' && msg.data.columns && msg.data.rows && (
              <div style={{ background: '#fff', borderRadius: 10, marginTop: 8, padding: 12, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #eee' }}>
                      {msg.data.columns.map(col => (
                        <th key={col} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: '#666' }}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {msg.data.rows.map((row, ri) => (
                      <tr key={ri} style={{ borderBottom: '1px solid #f0f0f0' }}>
                        {msg.data!.columns!.map(col => (
                          <td key={col} style={{ padding: '6px 10px' }}>{row[col]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', padding: '12px 16px', color: '#999', fontSize: 14 }}>
            思考中...
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="输入问题..."
          style={{
            flex: 1, padding: '12px 16px', borderRadius: 10, border: '1px solid #ddd',
            fontSize: 14, outline: 'none',
          }}
        />
        <button onClick={handleSend} disabled={loading} style={{
          padding: '12px 24px', borderRadius: 10, border: 'none',
          background: '#4f46e5', color: '#fff', fontSize: 14, fontWeight: 500,
          cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1,
        }}>
          发送
        </button>
      </div>
    </div>
  )
}
