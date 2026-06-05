import { useState, useRef, useEffect } from 'react'
import ReactEChartsCore from 'echarts-for-react'
import { api } from '../services/api'
import type { ChatResponse } from '../types'

interface Message {
  role: 'user' | 'assistant';
  content: string;
  data?: ChatResponse['data'];
}

export function AIChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '\u4f60\u597d\uff01\u6211\u662f\u6307\u6807\u8c03\u5ea6\u7cfb\u7edf\u7684 AI \u52a9\u624b\u3002\u4f60\u53ef\u4ee5\u95ee\u6211\uff1a\n- list indicators \u67e5\u770b\u6307\u6807\u5217\u8868\n- summary \u67e5\u770b\u7cfb\u7edf\u603b\u89c8\n- top values \u67e5\u770b\u6392\u540d\n- \u6216\u8005\u8f93\u5165\u4efb\u610f\u5173\u952e\u8bcd\u641c\u7d22\u76f8\u5173\u6307\u6807',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const res = await api.aiChat(text)
      const content = renderContent(res)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content, data: res.data },
      ])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '\u62b1\u6b49\uff0c\u67e5\u8be2\u51fa\u9519\u4e86\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002',
      }])
    } finally {
      setLoading(false)
    }
  }

  function renderContent(res: ChatResponse): string {
    if (res.intent === 'error') return 'Error: ' + JSON.stringify(res.data)

    const data = res.data
    if (data.type === 'text') return data.content || ''
    if (data.type === 'table') return `Found ${data.rows?.length || 0} records`
    if (data.type === 'bar' && data.title) return data.title
    return 'Query completed'
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
                  tooltip: {},
                  xAxis: { type: 'category', data: msg.data.categories, axisLabel: { rotate: 30 } },
                  yAxis: { type: 'value' },
                  series: [{ type: 'bar', data: msg.data.values, itemStyle: { color: '#4f46e5' } }],
                  grid: { left: 50, right: 20, bottom: 50, top: 10 },
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
            Thinking...
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Ask a question..."
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
          Send
        </button>
      </div>
    </div>
  )
}
