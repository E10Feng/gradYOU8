import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface StudentProfile {
  student: { name: string; id: string }
  courses: Array<{ id: string; title: string; credits: number; grade: string; semester: string }>
  gpa: number
  programs: Array<{ name: string; type: string }>
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; page_range: string; text: string }[]
}

const EXAMPLE_QUESTIONS = [
  "What are the gateway courses for the Biology major?",
  "Can BIOL 296 count toward my natural science distribution?",
  "What are the required courses for a Chemistry minor?",
  "How many credits do I need for the Biology major?",
  "What's the grade requirement for courses in the major?",
]

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
        thead: ({ children }) => <thead style={{ background: 'rgba(33, 87, 50, 0.25)' }}>{children}</thead>,
        tbody: ({ children }) => <tbody style={{ borderColor: 'rgba(33, 87, 50, 0.4)' }} className="divide-y">{children}</tbody>,
        tr: ({ children }) => <tr className="hover:bg-[rgba(33,87,50,0.2)]">{children}</tr>,
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

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [studentProfile, setStudentProfile] = useState<StudentProfile | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    try {
      const stored = localStorage.getItem('gradYOU8_profile')
      if (stored) {
        setStudentProfile(JSON.parse(stored))
      }
    } catch {
      // ignore
    }
  }, [])

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
      if (studentProfile) {
        body.profile = studentProfile
      }

      const streamRes = await fetch('/chat/stream', {
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
        if (studentProfile) body.profile = studentProfile
        const res = await fetch('/chat', {
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

  const profileActive = studentProfile !== null

  return (
    <div className="flex flex-col h-[calc(100vh-80px)]">
      {/* Header */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1" style={{ color: 'var(--text-primary)' }}>Ask about WashU requirements</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Powered by vectorless RAG over the WashU Undergraduate Bulletin</p>
        </div>
        {profileActive && (
          <div className="glass-chip flex items-center gap-2 px-3 py-1.5 rounded-full shrink-0">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs" style={{ color: 'var(--accent)' }}>
              {studentProfile.student?.name || 'Profile loaded'}
            </span>
          </div>
        )}
      </div>

      {/* Example questions */}
      <div className="flex flex-wrap gap-2 mb-6">
        {EXAMPLE_QUESTIONS.map(q => (
          <button
            key={q}
            onClick={() => send(q)}
            className="text-left px-3 py-1.5 rounded-full glass-chip text-sm interactive-lift transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto no-scrollbar glass surface-card rounded-2xl p-6 mb-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full" style={{ color: 'var(--text-muted)' }}>
            <svg viewBox="0 0 24 24" className="h-10 w-10 mb-3" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)' }} aria-hidden="true">
              <path d="M4.5 6.75A2.25 2.25 0 0 1 6.75 4.5h10.5a2.25 2.25 0 0 1 2.25 2.25v7.5a2.25 2.25 0 0 1-2.25 2.25H10l-4.5 3v-3H6.75A2.25 2.25 0 0 1 4.5 14.25v-7.5Z" />
            </svg>
            <p className="text-sm">Ask a question above, or type your own below.</p>
            {profileActive && (
              <p className="text-xs mt-2" style={{ color: 'var(--accent)' }}>
                Your profile is active — answers will consider your specific courses.
              </p>
            )}
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === 'assistant' && loading && !msg.content.trim() && (!msg.sources || msg.sources.length === 0)) {
            return null
          }
          return (
          <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
              msg.role === 'user'
                ? 'chat-bubble-user text-white rounded-br-md'
                : 'glass rounded-bl-md'
            }`} style={msg.role === 'assistant' ? { color: 'var(--text-primary)' } : undefined}>
              <div className="prose prose-invert prose-sm max-w-none">
                {msg.role === 'assistant' ? (
                  <MessageContent content={msg.content} />
                ) : (
                  <span>{msg.content}</span>
                )}
              </div>
            </div>
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
              <div className="max-w-[85%] text-xs">
                <p className="font-medium mb-2" style={{ color: 'var(--text-subtle)' }}>Sources:</p>
                <div className="space-y-2">
                  {msg.sources.map((s, j) => (
                    <div key={j} className="glass rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium" style={{ color: 'var(--accent)' }}>{s.title}</span>
                        <span className="font-mono text-xs" style={{ color: 'var(--text-subtle)' }}>pp. {s.page_range}</span>
                      </div>
                      <p className="text-xs line-clamp-2" style={{ color: 'var(--text-muted)' }}>{s.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          )
        })}

        {loading && (
          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
            <div className="w-4 h-4 spinner-green" />
            <span>{statusText || 'Working...'}</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); send(input) }}
        className="flex gap-3"
      >
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about any major, minor, or graduation requirement..."
          className="flex-1 glass-input rounded-xl px-4 py-3 text-sm"
          style={{ color: 'var(--text-primary)' }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="glass-button disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl text-sm font-medium"
        >
          Ask
        </button>
      </form>
    </div>
  )
}
