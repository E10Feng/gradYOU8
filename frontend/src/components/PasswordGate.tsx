import { useState, useEffect, useRef } from 'react'

const SESSION_KEY = 'gradYOU8_pw'

interface Props {
  children: React.ReactNode
}

async function checkPassword(pw: string): Promise<boolean> {
  try {
    const res = await fetch('/api/health', {
      headers: { Authorization: `Bearer ${pw}` },
    })
    return res.ok
  } catch {
    return false
  }
}

export function getStoredPassword(): string {
  return sessionStorage.getItem(SESSION_KEY) ?? ''
}

export default function PasswordGate({ children }: Props) {
  const [unlocked, setUnlocked] = useState(false)
  const [input, setInput] = useState('')
  const [error, setError] = useState(false)
  const [checking, setChecking] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // On mount, check if we already have a valid password in sessionStorage
  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY)
    if (stored) {
      checkPassword(stored).then(ok => {
        if (ok) setUnlocked(true)
        else sessionStorage.removeItem(SESSION_KEY)
      })
    }
  }, [])

  useEffect(() => {
    if (!unlocked) inputRef.current?.focus()
  }, [unlocked])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim()) return
    setChecking(true)
    setError(false)
    const ok = await checkPassword(input.trim())
    setChecking(false)
    if (ok) {
      sessionStorage.setItem(SESSION_KEY, input.trim())
      setUnlocked(true)
    } else {
      setError(true)
      setInput('')
      inputRef.current?.focus()
    }
  }

  if (unlocked) return <>{children}</>

  return (
    <div className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: 'var(--bg-base)' }}>
      <div className="w-full max-w-sm mx-4 rounded-2xl p-8 flex flex-col gap-6"
        style={{
          background: 'var(--glass-bg-strong)',
          border: '1px solid var(--glass-border-mid)',
          boxShadow: 'var(--glass-shadow)',
        }}>
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight"
            style={{ color: 'var(--text-primary)' }}>
            gradYOU8
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Enter the access password to continue.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            ref={inputRef}
            type="password"
            value={input}
            onChange={e => { setInput(e.target.value); setError(false) }}
            placeholder="Password"
            autoComplete="current-password"
            className="w-full rounded-lg px-4 py-2.5 text-sm outline-none transition-colors"
            style={{
              background: 'var(--glass-bg-ultra)',
              border: `1px solid ${error ? 'rgba(220,80,60,0.6)' : 'var(--glass-border)'}`,
              color: 'var(--text-primary)',
            }}
          />
          {error && (
            <p className="text-xs" style={{ color: 'rgba(220,100,80,0.9)' }}>
              Incorrect password. Try again.
            </p>
          )}
          <button
            type="submit"
            disabled={checking || !input.trim()}
            className="w-full rounded-lg py-2.5 text-sm font-medium transition-opacity disabled:opacity-40"
            style={{
              background: 'var(--glass-border-hot)',
              color: 'var(--text-primary)',
            }}>
            {checking ? 'Checking…' : 'Enter'}
          </button>
        </form>
      </div>
    </div>
  )
}
