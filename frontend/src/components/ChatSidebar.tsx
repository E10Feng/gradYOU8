import { apiFetch } from '../lib/api'
import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { StudentProfile } from './TranscriptUpload'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; page_range: string; text: string }[]
}

const EXAMPLE_QUESTIONS = [
  "What gateway courses do I still need for Biology?",
  "Can CSE 247 count toward my CS minor?",
  "How many more distribution credits do I need?",
  "What's my projected graduation timeline?",
]

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true" style={{ color: 'var(--accent)' }}>
      <path d="M4.5 6.75A2.25 2.25 0 0 1 6.75 4.5h10.5a2.25 2.25 0 0 1 2.25 2.25v7.5a2.25 2.25 0 0 1-2.25 2.25H10l-4.5 3v-3H6.75A2.25 2.25 0 0 1 4.5 14.25v-7.5Z" />
    </svg>
  )
}

function MessageContent({ content }: { content: string }) {
  const clean = content
    .replace(/<thinking[\s\S]*?<\/thinking>/gi, "")
    .replace(/\[\/?INST\]/gi, "")
    .trim()

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }) => (
          <table className="min-w-full text-xs border-collapse overflow-x-auto block">{children}</table>
        ),
        thead: ({ children }) => <thead style={{ background: 'var(--table-header-bg)' }}>{children}</thead>,
        tbody: ({ children }) => <tbody style={{ borderColor: 'var(--table-border)' }} className="divide-y">{children}</tbody>,
        tr: ({ children }) => <tr className="hover:opacity-80">{children}</tr>,
        th: ({ children }) => <th className="px-2 py-1 text-left font-medium" style={{ color: 'var(--accent)' }}>{children}</th>,
        td: ({ children }) => <td className="px-2 py-1" style={{ color: 'var(--text-muted)' }}>{children}</td>,
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>,
        li: ({ children }) => <li style={{ color: 'var(--text-muted)' }}>{children}</li>,
        strong: ({ children }) => <strong className="font-semibold" style={{ color: 'var(--text-primary)' }}>{children}</strong>,
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-1" style={{ color: 'var(--text-primary)' }}>{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-semibold mt-3 mb-1" style={{ color: 'var(--text-primary)' }}>{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1" style={{ color: 'var(--accent)' }}>{children}</h3>,
        blockquote: ({ children }) => <blockquote className="border-l-2 pl-3 italic" style={{ borderColor: 'var(--accent)', color: 'var(--text-muted)' }}>{children}</blockquote>,
      }}
    >
      {clean}
    </ReactMarkdown>
  )
}

interface Props {
  profile: StudentProfile | null
}

export default function ChatSidebar({ profile }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusText, setStatusText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(question: string) {
    if (!question.trim() || loading) return
    setLoading(true)
    setStatusText('')

    const userMsg: Message = { id: `user-${Date.now()}`, role: 'user', content: question }
    const assistantId = `assistant-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setMessages(prev => [...prev, userMsg, { id: assistantId, role: 'assistant', content: '', sources: [] }])
    setInput('')

    try {
      const body: Record<string, unknown> = { question }
      if (profile) {
        body.profile = profile
      }
      const streamRes = await apiFetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify(body),
      })

      const isSse = (streamRes.headers.get('content-type') || '').includes('text/event-stream')
      if (!streamRes.ok || !streamRes.body || !isSse) {
        throw new Error('Streaming unavailable')
      }

      const reader = streamRes.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamDone = false

      const appendAssistantText = (text: string) => {
        setMessages(prev => prev.map(m => (
          m.id === assistantId ? { ...m, content: `${m.content}${text}` } : m
        )))
      }

      const setAssistantSources = (sources: { title: string; page_range: string; text: string }[]) => {
        setMessages(prev => prev.map(m => (
          m.id === assistantId ? { ...m, sources } : m
        )))
      }

      const processEventBlock = (block: string) => {
        const lines = block.split('\n')
        let eventName = 'message'
        const dataLines: string[] = []
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (dataLines.length === 0) return
        let payload: any = {}
        try {
          payload = JSON.parse(dataLines.join('\n'))
        } catch {
          return
        }

        if (eventName === 'status') {
          setStatusText(payload.message || 'Thinking...')
        } else if (eventName === 'answer_delta') {
          appendAssistantText(payload.text || '')
        } else if (eventName === 'sources') {
          setAssistantSources(payload.sources || [])
        } else if (eventName === 'error') {
          throw new Error(payload.message || 'Streaming error')
        } else if (eventName === 'done') {
          streamDone = true
        }
      }

      while (!streamDone) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')
        let splitIndex = buffer.indexOf('\n\n')
        while (splitIndex !== -1) {
          const block = buffer.slice(0, splitIndex).trim()
          buffer = buffer.slice(splitIndex + 2)
          if (block) processEventBlock(block)
          splitIndex = buffer.indexOf('\n\n')
        }
      }

      setMessages(prev => prev.map(m => (
        m.id === assistantId && !m.content.trim()
          ? { ...m, content: "I couldn't find an answer. Try rephrasing your question." }
          : m
      )))
    } catch (err) {
      setStatusText('Retrying without streaming...')
      try {
        const body: Record<string, unknown> = { question }
        if (profile) body.profile = profile
        const res = await apiFetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!res.ok) throw new Error(`Server error: ${res.status}`)
        const data = await res.json()
        setMessages(prev => prev.map(m => (
          m.id === assistantId
            ? {
              ...m,
              content: data.answer || "I couldn't find an answer. Try rephrasing your question.",
              sources: data.sources || [],
            }
            : m
        )))
      } catch (fallbackErr) {
        const msg = fallbackErr instanceof Error ? fallbackErr.message : (err instanceof Error ? err.message : 'Failed to get response')
        setMessages(prev => prev.map(m => (
          m.id === assistantId
            ? { ...m, content: `Error: ${msg}` }
            : m
        )))
      }
    } finally {
      setLoading(false)
      setStatusText('')
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="px-4 pt-4 pb-3">
        <h2 className="font-semibold text-base tracking-tight mb-1" style={{ color: 'var(--text-primary)' }}>Degree Advisor</h2>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Ask about your requirements</p>
      </div>

      {/* Quick questions */}
      {messages.length === 0 && (
        <div className="px-4 pb-4 flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map(q => (
            <button
              key={q}
              onClick={() => send(q)}
              className="text-left px-2.5 py-1 rounded-full glass-chip text-xs transition-colors interactive-lift"
            style={{ color: 'var(--text-muted)' }}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar px-4 space-y-3">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full py-8" style={{ color: 'var(--text-muted)' }}>
            <div className="mb-2"><ChatIcon /></div>
            <p className="text-xs text-center">Ask about your degree requirements.</p>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === 'assistant' && loading && !msg.content.trim() && (!msg.sources || msg.sources.length === 0)) {
            return null
          }
          return (
          <div key={msg.id} className={`flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[90%] rounded-xl px-3 py-2 text-xs ${
              msg.role === 'user'
                ? 'chat-bubble-user text-white rounded-br-sm'
                : 'glass rounded-bl-sm'
            }`}>
              {msg.role === 'assistant' ? (
                <MessageContent content={msg.content} />
              ) : (
                <span>{msg.content}</span>
              )}
            </div>
          </div>
          )
        })}

        {loading && (
          <div className="flex items-center gap-2 text-xs py-2" style={{ color: 'var(--text-muted)' }}>
            <div className="w-3 h-3 spinner-green" />
            <span>{statusText || 'Working...'}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); send(input) }}
        className="p-3 border-t"
        style={{ borderTopColor: 'var(--glass-border)' }}
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask about requirements..."
            className="flex-1 glass-input rounded-full px-3 py-2 text-xs"
            style={{ color: 'var(--text-primary)' }}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="glass-button disabled:opacity-50 disabled:cursor-not-allowed text-white px-3 py-2 rounded-full text-xs font-medium shrink-0"
          >
            →
          </button>
        </div>
      </form>
    </div>
  )
}
