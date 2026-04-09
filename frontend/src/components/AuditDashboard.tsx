import { useState, useEffect } from 'react'
import ProgressBar from './ProgressBar'
import RequirementGroup from './RequirementGroup'
import { StudentProfile } from './TranscriptUpload'

interface AuditGroup {
  name: string
  status: 'SATISFIED' | 'PARTIAL' | 'MISSING'
  percent: number
  satisfied: string[]
  remaining: string[]
  credit_progress: string
}

interface AuditResult {
  program: string
  school: string
  overall_percent: number
  notes?: string[]
  groups: AuditGroup[]
  error?: string
  is_college?: boolean
}

interface Props {
  profile: StudentProfile
}

export default function AuditDashboard({ profile }: Props) {
  const [audits, setAudits] = useState<AuditResult[]>([])
  const [collegeAudit, setCollegeAudit] = useState<AuditResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [progressMsg, setProgressMsg] = useState<string>('Running degree audit...')

  useEffect(() => {
    async function runAudits() {
      setLoading(true)
      setError(null)
      setProgressMsg('Running degree audit...')
      setAudits([])
      setCollegeAudit(null)

      try {
        const streamRes = await fetch('/api/audit-full/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({
            courses: profile.courses,
            programs: profile.programs,
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
          let payload: Record<string, any>
          try {
            payload = JSON.parse(dataLines.join('\n'))
          } catch {
            return
          }

          if (eventName === 'status') {
            setProgressMsg(payload.message || 'Running degree audit...')
          } else if (eventName === 'program_complete') {
            const result = payload.result as AuditResult | undefined
            if (result) {
              setAudits(prev => {
                const idx = prev.findIndex(a => a.program === result.program)
                if (idx === -1) return [...prev, result]
                const copy = [...prev]
                copy[idx] = result
                return copy
              })
            }
            const done = Number(payload.completed_count || 0)
            const total = Number(payload.total_programs || 0)
            setProgressMsg(`Completed ${done}/${total} program audits...`)
          } else if (eventName === 'college_complete') {
            const result = payload.result as AuditResult | undefined
            if (result) setCollegeAudit(result)
            setProgressMsg('Finalizing college requirements...')
          } else if (eventName === 'result') {
            const finalAudits = (payload.audits as AuditResult[]) || []
            setAudits(finalAudits)
            if (payload.college_audit) setCollegeAudit(payload.college_audit as AuditResult)
          } else if (eventName === 'error') {
            throw new Error(payload.message || 'Audit stream error')
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
      } catch (err) {
        try {
          const res = await fetch('/api/audit-full', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              courses: profile.courses,
              programs: profile.programs,
            }),
          })
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}))
            throw new Error(errData.detail || `Audit failed (${res.status})`)
          }
          const data = await res.json()
          setAudits(data.audits || [])
          if (data.college_audit) setCollegeAudit(data.college_audit)
        } catch (fallbackErr) {
          const msg = fallbackErr instanceof Error ? fallbackErr.message : 'Failed to run audit'
          setError(msg)
        }
      } finally {
        setLoading(false)
      }
    }

    runAudits()
  }, [profile])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">{progressMsg}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-6 py-4 text-red-400 text-sm">
        {error}
      </div>
    )
  }

  if (audits.length === 0 && !collegeAudit) {
    return (
      <div className="text-slate-400 text-sm text-center py-12">
        No program audits available. Make sure your transcript was parsed correctly.
      </div>
    )
  }

  const gpaColor = profile.gpa >= 3.5 ? 'text-emerald-400' : profile.gpa >= 3.0 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="flex flex-col gap-8">
      {/* Student summary */}
      <div className="bg-slate-900 rounded-xl p-6 border border-slate-800 flex flex-wrap gap-6">
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Student</p>
          <p className="text-white font-semibold">{profile.student?.name || 'Unknown'}</p>
          <p className="text-slate-400 text-xs">{profile.student?.id || ''}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">GPA</p>
          <p className={`text-2xl font-bold font-mono ${gpaColor}`}>
            {profile.gpa ? profile.gpa.toFixed(2) : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">Programs</p>
          {profile.programs.map((p, i) => (
            <p key={i} className="text-white text-sm">
              {p.name} <span className="text-slate-500 text-xs">({p.type})</span>
            </p>
          ))}
        </div>
      </div>

      {/* Per-program audit results */}
      {audits.map((audit, i) => (
        <ProgramAuditCard key={i} audit={audit} />
      ))}

      {/* College-level graduation requirements */}
      {collegeAudit && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-xs text-slate-500 uppercase tracking-widest">College Requirements</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>
          <ProgramAuditCard audit={collegeAudit} isCollege />
        </div>
      )}
    </div>
  )
}

function ProgramAuditCard({ audit, isCollege = false }: { audit: AuditResult; isCollege?: boolean }) {
  const pctColor =
    audit.overall_percent >= 80
      ? 'text-emerald-400'
      : audit.overall_percent >= 40
      ? 'text-amber-400'
      : 'text-red-400'

  const barColor =
    audit.overall_percent >= 80
      ? 'bg-emerald-500'
      : audit.overall_percent >= 40
      ? 'bg-amber-500'
      : 'bg-red-500'

  return (
    <div className="flex flex-col gap-4">
      {/* Program header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className={`font-bold text-white ${isCollege ? 'text-base' : 'text-lg'}`}>
            {audit.program}
          </h2>
          {audit.school && <p className="text-xs text-slate-500">{audit.school}</p>}
        </div>
        <div className="flex flex-col items-end">
          <span className="text-xs text-slate-500 uppercase tracking-wide">Overall</span>
          <span className={`text-2xl font-bold font-mono ${pctColor}`}>{audit.overall_percent}%</span>
        </div>
      </div>

      {audit.error ? (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-4 py-3 text-amber-400 text-sm">
          {audit.error}
        </div>
      ) : (
        <>
          {audit.notes && audit.notes.length > 0 && (
            <div className="bg-indigo-500/10 border border-indigo-500/30 rounded-lg px-4 py-3 text-indigo-200 text-sm">
              <p className="text-indigo-300 text-xs uppercase tracking-wide mb-2">Notes</p>
              <div className="space-y-1">
                {audit.notes.slice(0, 6).map((n, idx) => (
                  <p key={idx}>- {n}</p>
                ))}
              </div>
            </div>
          )}

          <ProgressBar label="Degree Completion" percent={audit.overall_percent} color={barColor} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {audit.groups.map((group, j) => (
              <RequirementGroup key={j} group={group} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
