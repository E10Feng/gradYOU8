import { useState, useEffect, type MouseEvent as ReactMouseEvent } from 'react'
import TranscriptUpload, { StudentProfile } from '../components/TranscriptUpload'
import TimelineView from '../components/TimelineView'
import ChatSidebar from '../components/ChatSidebar'
import RequirementGroup from '../components/RequirementGroup'
import ProgressBar from '../components/ProgressBar'
import ThemeButton from '../components/ThemeButton'

interface AuditResult {
  program: string
  school: string
  overall_percent: number
  notes?: string[]
  unstructured_compare?: boolean
  groups: Array<{
    name: string
    status: 'SATISFIED' | 'PARTIAL' | 'MISSING'
    percent: number
    satisfied: string[]
    remaining: string[]
    credit_progress: string
  }>
  error?: string
  is_college?: boolean
}

type ViewMode = 'timeline' | 'audit'

type AuditProgressItem = {
  name: string
  overallPercent: number
  hasError: boolean
}

type AuditProgressState = {
  phase: string
  message: string
  pendingNames: string[]
  completed: AuditProgressItem[]
  collegePending: boolean
}

function EmptyStateIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true" style={{ color: 'var(--accent)' }}>
      <path d="M3 8.5L12 4l9 4.5-9 4.5L3 8.5Z" />
      <path d="M7 10.5v4.25c0 1.1 2.24 2.25 5 2.25s5-1.15 5-2.25V10.5" />
      <path d="M21 8.5v5.5" />
    </svg>
  )
}


export default function Profile() {
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [view, setView] = useState<ViewMode>('audit')
  const [audits, setAudits] = useState<AuditResult[]>([])
  const [collegeAudit, setCollegeAudit] = useState<AuditResult | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [auditProgress, setAuditProgress] = useState<AuditProgressState | null>(null)
  const [auditStarted, setAuditStarted] = useState(false)
  const [uploadSession, setUploadSession] = useState(0)
  const [sidebarVisible, setSidebarVisible] = useState(true)
  const [sidebarWidth, setSidebarWidth] = useState(360)
  const [timelineExpandAll, setTimelineExpandAll] = useState(true)

  // Load profile + cached audit results from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('gradYOU8_profile')
      if (stored) {
        const p = JSON.parse(stored)
        setProfile(p)
        setAuditStarted(true)

        // Restore cached audit results instead of re-running
        const cachedAudits = localStorage.getItem('gradYOU8_audits')
        const cachedCollege = localStorage.getItem('gradYOU8_college_audit')
        if (cachedAudits) {
          try { setAudits(JSON.parse(cachedAudits)) } catch { /* ignore */ }
        }
        if (cachedCollege) {
          try { setCollegeAudit(JSON.parse(cachedCollege)) } catch { /* ignore */ }
        }

        // Only run audits if there are no cached results
        if (!cachedAudits) {
          runAudits(p)
        }
      }
    } catch {
      // ignore
    }
  }, [])

  // Persist audit results to localStorage
  useEffect(() => {
    if (audits.length > 0) {
      localStorage.setItem('gradYOU8_audits', JSON.stringify(audits))
    }
  }, [audits])

  useEffect(() => {
    if (collegeAudit) {
      localStorage.setItem('gradYOU8_college_audit', JSON.stringify(collegeAudit))
    }
  }, [collegeAudit])

  async function runAudits(p: StudentProfile) {
    setAuditLoading(true)
    setAuditError(null)
    setAudits([])
    setCollegeAudit(null)
    setView('audit')
    const programNames = (p.programs || []).map(pr => pr.name).filter(Boolean) as string[]
    setAuditProgress({
      phase: 'programs',
      message: 'Starting audit…',
      pendingNames: programNames,
      completed: [],
      collegePending: false,
    })

    const applyAuditPayload = (data: { audits?: AuditResult[]; college_audit?: AuditResult | null }) => {
      setAudits(data.audits || [])
      setCollegeAudit(data.college_audit ?? null)
    }

    try {
      const streamRes = await fetch('/api/audit-full/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          courses: p.courses,
          programs: p.programs,
          student: p.student,
          gpa: p.gpa,
        }),
      })

      const isSse = (streamRes.headers.get('content-type') || '').includes('text/event-stream')
      if (!streamRes.ok || !streamRes.body || !isSse) {
        throw new Error('Stream unavailable')
      }

      const reader = streamRes.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamDone = false

      const processEventBlock = (block: string) => {
        const lines = block.split('\n')
        let eventName = 'message'
        const dataLines: string[] = []
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (dataLines.length === 0) return
        let payload: Record<string, unknown>
        try {
          payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
        } catch {
          return
        }

        if (eventName === 'status') {
          const msg = (payload.message as string) || ''
          const phase = (payload.phase as string) || 'programs'
          const pending = (payload.pending as string[]) || undefined
          setAuditProgress(prev => {
            if (!prev) {
              return {
                phase,
                message: msg,
                pendingNames: pending ?? programNames,
                completed: [],
                collegePending: phase === 'college',
              }
            }
            return {
              ...prev,
              phase,
              message: msg,
              pendingNames: pending ?? prev.pendingNames,
              collegePending: phase === 'college',
            }
          })
        } else if (eventName === 'program_complete') {
          const name = payload.program as string
          const overallPercent = Number(payload.overall_percent) || 0
          const hasError = Boolean(payload.has_error)
          const programResult = payload.result as AuditResult | undefined
          if (programResult) {
            setAudits(prev => {
              const idx = prev.findIndex(a => a.program === programResult.program)
              if (idx === -1) return [...prev, programResult]
              const copy = [...prev]
              copy[idx] = programResult
              return copy
            })
          }
          setAuditProgress(prev => {
            if (!prev) return prev
            const done = prev.completed.some(c => c.name === name)
            const nextCompleted = done
              ? prev.completed.map(c => (c.name === name ? { ...c, overallPercent, hasError } : c))
              : [...prev.completed, { name, overallPercent, hasError }]
            return {
              ...prev,
              message: `Completed ${name.split(',')[0]}…`,
              completed: nextCompleted,
              pendingNames: prev.pendingNames.filter(n => n !== name),
            }
          })
        } else if (eventName === 'college_complete') {
          const collegeResult = payload.result as AuditResult | undefined
          if (collegeResult) setCollegeAudit(collegeResult)
          setAuditProgress(prev => (prev ? {
            ...prev,
            phase: 'college',
            collegePending: false,
            message: `College audit: ${(payload.program as string) || 'done'}`,
          } : prev))
        } else if (eventName === 'result') {
          applyAuditPayload(payload as unknown as { audits: AuditResult[]; college_audit: AuditResult | null })
        } else if (eventName === 'error') {
          throw new Error((payload.message as string) || 'Audit stream error')
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
          const chunk = buffer.slice(0, splitIndex).trim()
          buffer = buffer.slice(splitIndex + 2)
          if (chunk) processEventBlock(chunk)
          splitIndex = buffer.indexOf('\n\n')
        }
      }
      setAuditProgress(null)
    } catch {
      setAuditProgress(prev => prev ? { ...prev, message: 'Retrying without live progress…' } : prev)
      try {
        const res = await fetch('/api/audit-full', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            courses: p.courses,
            programs: p.programs,
            student: p.student,
            gpa: p.gpa,
          }),
        })
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error((errData as { detail?: string }).detail || `Audit failed (${res.status})`)
        }
        const data = await res.json()
        applyAuditPayload(data)
      } catch (err) {
        setAuditError(err instanceof Error ? err.message : 'Failed to run audit')
      } finally {
        setAuditProgress(null)
      }
    } finally {
      setAuditLoading(false)
    }
  }

  function handleProfileLoaded(p: StudentProfile) {
    setProfile(p)
    localStorage.setItem('gradYOU8_profile', JSON.stringify(p))
    setAuditStarted(false)
    setAuditError(null)
    setAudits([])
    setCollegeAudit(null)
  }

  function handleStartAudit() {
    if (!profile || auditLoading) return
    setAuditStarted(true)
    runAudits(profile)
  }

  function handleUploadAnother() {
    setProfile(null)
    setAuditStarted(false)
    setAudits([])
    setCollegeAudit(null)
    setAuditError(null)
    setView('audit')
    setTimelineExpandAll(true)
    setSidebarVisible(true)
    localStorage.removeItem('gradYOU8_profile')
    localStorage.removeItem('gradYOU8_audits')
    localStorage.removeItem('gradYOU8_college_audit')
    setUploadSession(prev => prev + 1)
  }

  const profileActive = profile !== null && auditStarted
  const minSidebarWidth = 280
  const maxSidebarWidth = 640

  function startSidebarResize(e: ReactMouseEvent<HTMLElement>) {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = sidebarWidth

    const onMouseMove = (event: MouseEvent) => {
      const delta = startX - event.clientX
      const nextWidth = Math.min(maxSidebarWidth, Math.max(minSidebarWidth, startWidth + delta))
      setSidebarWidth(nextWidth)
    }

    const onMouseUp = () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  // ── Shared Header ────────────────────────────────────────────────
  function renderHeader() {
    if (!profile) return null
    const { student, gpa, programs } = profile
    const gpaColor = gpa >= 3.5 ? 'var(--accent-emerald)' : gpa >= 3.0 ? 'var(--accent-amber)' : 'var(--accent-red)'

    return (
      <div className="glass surface-card glass-prism rounded-3xl px-6 py-5 profile-enter-1">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Student info */}
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <p className="font-semibold text-xl leading-tight tracking-tight" style={{ color: 'var(--text-primary)', fontFamily: "'Fraunces', serif", fontStyle: 'italic' }}>{student.name || 'Unknown'}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>ID: {student.id || '—'} · {student.school || '—'}</p>
            </div>
            <div className="h-8 w-px hidden sm:block" style={{ background: 'var(--glass-border)' }} />
            <div>
              <p className="text-xs uppercase tracking-wide mb-0.5" style={{ color: 'var(--text-subtle)' }}>GPA</p>
              <p className="text-xl font-bold font-mono" style={{ color: gpaColor }}>
                {gpa ? gpa.toFixed(2) : '—'}
              </p>
            </div>
            <div className="h-8 w-px hidden sm:block" style={{ background: 'var(--glass-border)' }} />
            <div className="flex flex-wrap gap-1.5">
              {programs.map((p, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{
                    background: 'var(--satisfied-bg)',
                    border: '1px solid var(--satisfied-border)',
                    color: 'var(--satisfied-color)',
                  }}
                >
                  {p.type === 'minor' ? 'Minor' : 'Major'}: {p.name.split(',')[0].split(' with ')[0].trim()}
                </span>
              ))}
            </div>
          </div>

          {/* View toggle + re-audit */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 glass-chip rounded-full p-1">
              <button
                onClick={() => setView('timeline')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium ${view === 'timeline' ? 'glass-button text-white' : 'transition-colors'}`}
                style={view !== 'timeline' ? { color: 'var(--text-muted)' } : undefined}
              >
                Timeline
              </button>
              <button
                onClick={() => setView('audit')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium ${view === 'audit' ? 'glass-button text-white' : 'transition-colors'}`}
                style={view !== 'audit' ? { color: 'var(--text-muted)' } : undefined}
              >
                Audit
              </button>
            </div>
            <button
              type="button"
              onClick={() => { if (profile && !auditLoading) runAudits(profile) }}
              disabled={auditLoading}
              className="px-3.5 py-1.5 rounded-full text-xs font-medium glass-chip transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ color: 'var(--text-muted)' }}
              title="Re-run degree audit"
            >
              {auditLoading ? 'Auditing…' : 'Re-audit'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Timeline View ────────────────────────────────────────────────
  function renderTimeline() {
    if (!profile) return null
    return (
      <div>
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm" style={{ color: 'var(--text-muted)' }}>Course progress by semester</h2>
          <button
            type="button"
            onClick={() => setTimelineExpandAll(prev => !prev)}
            className="text-xs px-3 py-1.5 rounded-full glass-chip transition-colors"
            style={{ color: 'var(--text-muted)' }}
          >
            {timelineExpandAll ? 'Collapse all courses' : 'Expand all courses'}
          </button>
        </div>
        <TimelineView profile={profile} expandAll={timelineExpandAll} />
      </div>
    )
  }

  // ── Audit View ──────────────────────────────────────────────────
  function renderAudit() {
    if (auditLoading) {
      const waiting = auditProgress?.pendingNames.filter(
        n => !auditProgress.completed.some(c => c.name === n),
      ) ?? []
      const shortLabel = (s: string) => s.split(',')[0].split(' with ')[0].trim()
      return (
        <div className="glass surface-card rounded-2xl p-6 space-y-5 max-w-2xl">
          <div className="progress-track h-1.5 w-full glass-shimmer">
            <div className="h-full progress-fill" style={{ width: '40%', maxWidth: '70%' }} />
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {auditProgress?.message || 'Running degree audit…'}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              {auditProgress?.phase === 'college'
                ? 'College-wide requirements'
                : 'Majors & minors'}
            </p>
          </div>
          {auditProgress && (auditProgress.completed.length > 0 || waiting.length > 0 || auditProgress.collegePending) && (
            <ul className="space-y-2">
              {auditProgress.completed.map(c => (
                <li key={c.name} className="flex items-center gap-2 text-xs">
                  <span aria-hidden>
                    {c.hasError ? '⚠' : '✓'}
                  </span>
                  <span className="flex-1 min-w-0 truncate" style={{ color: 'var(--text-muted)' }}>{shortLabel(c.name)}</span>
                  <span className="font-mono tabular-nums" style={{ color: 'var(--text-subtle)' }}>{c.overallPercent}%</span>
                </li>
              ))}
              {waiting.map(n => (
                <li key={n} className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <span className="h-3.5 w-3.5 shrink-0 spinner-green" />
                  <span className="truncate">{shortLabel(n)}</span>
                  <span className="ml-auto" style={{ color: 'var(--text-subtle)' }}>In progress</span>
                </li>
              ))}
              {auditProgress.phase === 'college' && auditProgress.collegePending && (
                <li className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  <span className="h-3.5 w-3.5 shrink-0 spinner-green" />
                  <span>College graduation requirements</span>
                </li>
              )}
            </ul>
          )}
          {!auditProgress && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
              <div className="w-8 h-8 spinner-green" />
              <span>Running degree audit…</span>
            </div>
          )}
        </div>
      )
    }

    if (auditError) {
      return (
        <div className="glass rounded-xl px-6 py-4 text-sm border" style={{ color: 'var(--accent-red)', borderColor: 'var(--accent-red)' }}>
          {auditError}
        </div>
      )
    }

    if (audits.length === 0 && !collegeAudit) {
      return (
        <div className="text-sm text-center py-12" style={{ color: 'var(--text-muted)' }}>
          No audit results available. Make sure your transcript was parsed correctly.
        </div>
      )
    }

    function renderAuditCard(audit: AuditResult, label?: string) {
      const isCollege = audit.is_college
      const cardBorderColor = 'var(--glass-border)'
      const labelColor = isCollege ? 'var(--accent)' : 'var(--satisfied-color)'
      const labelBg = isCollege ? 'var(--glass-bg)' : 'var(--satisfied-bg)'

      return (
        <div key={label || audit.program} className="glass surface-card rounded-xl p-6 interactive-lift glass-glow" style={{ borderColor: cardBorderColor }}>
          {/* Header */}
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              {label && (
                <span className="text-xs px-2 py-0.5 rounded-full font-medium mb-1 inline-block" style={{ background: labelBg, color: labelColor }}>
                  {label}
                </span>
              )}
              <h3 className="font-semibold" style={{ color: 'var(--text-primary)', fontFamily: "'Fraunces', serif", fontStyle: 'italic' }}>{audit.program}</h3>
              {audit.school && (
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{audit.school}</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-1 shrink-0">
              <span className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>Overall</span>
              <span className="text-2xl font-bold font-mono" style={{
                color: audit.overall_percent >= 80 ? 'var(--accent-emerald)'
                : audit.overall_percent >= 40 ? 'var(--accent-amber)'
                : 'var(--accent-red)'
              }}>
                {audit.overall_percent}%
              </span>
            </div>
          </div>

          {audit.error ? (
            <div className="glass rounded-lg px-4 py-3 text-sm border" style={{ color: 'var(--accent-amber)', borderColor: 'var(--accent-amber)' }}>
              {audit.error}
            </div>
          ) : (
            <>
              {/* Overall progress bar */}
              <ProgressBar
                label="Degree Completion"
                percent={audit.overall_percent}
                color={
                  audit.overall_percent >= 80 ? 'bg-emerald-500'
                  : audit.overall_percent >= 40 ? 'bg-amber-500'
                  : 'bg-red-500'
                }
              />

              {/* Requirement groups */}
              {audit.groups && audit.groups.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                  {audit.groups.map((group, j) => (
                    <RequirementGroup key={j} group={group} />
                  ))}
                </div>
              )}

              {/* Notes (if any) */}
              {audit.notes && audit.notes.length > 0 && (
                <div className="glass rounded-lg px-4 py-3 text-xs mt-3" style={{ color: 'var(--text-muted)' }}>
                  {audit.notes.map((note, i) => (
                    <p key={i}>- {note}</p>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )
    }

    return (
      <div className="flex flex-col gap-6">
        {/* College requirements first */}
        {collegeAudit && renderAuditCard(collegeAudit, 'College Requirements')}

        {/* Per-program audits */}
        {audits.map((audit, i) => {
          const prog = profile?.programs[i]
          const label = prog?.type === 'minor' ? 'Minor' : 'Major'
          return renderAuditCard(audit, label)
        })}
      </div>
    )
  }

  // ── Main Layout ─────────────────────────────────────────────────
  return (
    <div className="flex gap-0 h-full">
      {/* Main content area */}
      <div className={`flex-1 flex flex-col gap-6 min-w-0 transition-all ${sidebarVisible && profileActive ? 'pr-[380px]' : ''}`}>
        {/* Page header */}
        <div className="flex items-start justify-between gap-3 profile-enter-1">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight mb-1" style={{ color: 'var(--text-primary)', fontFamily: "'Fraunces', serif", fontStyle: 'italic' }}>gradYOU8</h1>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-muted)' }}>
              {profileActive
                ? 'Review your student profile and degree progress.'
                : 'Upload your transcript to build your profile, then start your audit.'}
            </p>
          </div>
          {profileActive && (
            <div className="flex items-center gap-2 shrink-0">
              <ThemeButton />
              {!sidebarVisible && (
                <button
                  type="button"
                  onClick={() => setSidebarVisible(true)}
                  className="text-xs px-3.5 py-1.5 rounded-full glass-chip transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  Show chat
                </button>
              )}
              <button
                type="button"
                onClick={handleUploadAnother}
                className="text-xs px-3.5 py-1.5 rounded-full glass-chip transition-colors"
                style={{ color: 'var(--text-muted)' }}
              >
                Upload another transcript
              </button>
            </div>
          )}
        </div>

        {/* Upload */}
        {!auditStarted && (
          <div className="flex flex-col gap-4">
            <TranscriptUpload key={uploadSession} onProfileLoaded={handleProfileLoaded} />

            {profile && (
              <div className="glass surface-card rounded-xl px-4 py-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    Profile ready for {profile.student?.name || 'student'}.
                  </p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Start the audit to load requirements and progress.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleStartAudit}
                  disabled={auditLoading}
                  className="glass-button disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-full text-sm font-medium"
                >
                  Start audit
                </button>
              </div>
            )}
          </div>
        )}

        {/* Profile + view only shown after upload */}
        {profileActive && (
          <>
            {/* Shared header */}
            {renderHeader()}

            {/* Timeline or Audit view */}
            <div>
              {view === 'timeline' ? renderTimeline() : renderAudit()}
            </div>
          </>
        )}

        {!profile && (
          <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--text-muted)' }}>
            <div className="mb-4"><EmptyStateIcon /></div>
            <p className="text-sm">Upload your transcript above to get started.</p>
          </div>
        )}
      </div>

      {/* Chat sidebar panel — only when visible */}
      {profileActive && sidebarVisible && (
        <div
          className="fixed top-4 right-0 flex items-stretch z-30 mr-2"
          style={{ width: `${sidebarWidth}px`, height: 'calc(100vh - 2rem)' }}
        >
          <div className="relative ml-2 flex-1">
            <div
              onMouseDown={startSidebarResize}
              className="absolute -left-2 top-0 h-full w-3 cursor-col-resize"
              aria-label="Resize chat sidebar"
              title="Drag to resize"
            />
            <div
              className="glass-strong surface-elevated glass-prism rounded-2xl overflow-hidden flex flex-col h-full"
              style={{ width: '100%' }}
            >
              <div className="flex justify-end px-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSidebarVisible(false)}
                  className="text-xs px-2.5 py-1 rounded-full glass-chip transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  Hide chat
                </button>
              </div>
              <div className="flex-1 min-h-0">
                <ChatSidebar profile={profile} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
