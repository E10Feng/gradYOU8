import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: { title: string; page_range: string; text: string }[]
}

const EXAMPLE_QUESTIONS = [
  "What are the gateway courses for the Biology major?",
  "Can BIOL 296 count toward my natural science distribution?",
  "What are the required courses for a Chemistry minor?",
  "How many units do I need total for the Biology major?",
  "What's the grade requirement for courses in the major?",
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [indexStatus, setIndexStatus] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/tree')
      .then(r => r.json())
      .then(d => setIndexStatus(`${d.num_nodes} sections indexed`))
      .catch(() => setIndexStatus('Not indexed — POST /ingest to start'))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(question: string) {
    if (!question.trim() || loading) return
    setLoading(true)

    const userMsg: Message = { role: 'user', content: question }
    setMessages(prev => [...prev, userMsg])
    setInput('')

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, chat_history: [] }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Error connecting to the backend. Make sure the server is running.',
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Ask about WashU requirements</h1>
        <p className="text-slate-400 text-sm">
          Powered by vectorless RAG over the WashU Undergraduate Bulletin.
          <span className="ml-2 text-slate-600">{indexStatus}</span>
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {EXAMPLE_QUESTIONS.map(q => (
          <button
            key={q}
            onClick={() => send(q)}
            className="text-left px-4 py-3 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-300 hover:border-slate-700 hover:text-white transition"
          >
            {q}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4 bg-slate-900 rounded-xl p-4 min-h-[300px]">
        {messages.length === 0 && !loading && (
          <p className="text-slate-500 text-sm text-center py-8">
            Ask a question above, or type your own below.
          </p>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-100'
            }`}>
              {msg.content}
            </div>
            {msg.sources && msg.sources.length > 0 && (
              <div className="max-w-[80%] text-xs text-slate-500">
                <p className="font-medium mb-1">Sources:</p>
                {msg.sources.map((s, j) => (
                  <div key={j} className="bg-slate-800 rounded p-2 mb-1">
                    <p className="text-slate-400">{s.title} (pp. {s.page_range})</p>
                    <p className="text-slate-500 mt-1 line-clamp-2">{s.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={e => { e.preventDefault(); send(input) }}
        className="flex gap-3"
      >
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about any major, minor, or graduation requirement..."
          className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-3 rounded-lg text-sm font-medium transition"
        >
          Ask
        </button>
      </form>
    </div>
  )
}
