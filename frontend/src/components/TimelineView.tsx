import { useEffect, useRef, useState, type WheelEvent } from 'react'
import { StudentProfile, Semester, Course } from './TranscriptUpload'

interface TimelineViewProps {
  profile: StudentProfile
  expandAll?: boolean
}

function SeasonIcon({ season }: { season: string }) {
  const accent =
    season === 'Fall' ? 'text-red-300' :
    season === 'Spring' ? 'text-emerald-200' :
    season === 'Summer' ? 'text-emerald-300' :
    season === 'Winter' ? 'text-slate-200' :
    'text-emerald-300'
  return (
    <svg viewBox="0 0 24 24" className={`h-5 w-5 ${accent}`} fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M8 3.5v3M16 3.5v3M4 9.5h16" />
    </svg>
  )
}

function gradeColor(grade: string): string {
  if (!grade || grade === 'CR' || grade === 'P') return 'text-slate-400'
  const g = grade.replace('+', '').replace('-', '').replace('CR', '').replace('P', '').trim()
  switch (g) {
    case 'A': return 'text-emerald-400'
    case 'B': return 'text-emerald-300'
    case 'C': return 'text-amber-400'
    case 'D': return 'text-orange-400'
    case 'F': return 'text-red-400'
    default: return 'text-slate-400'
  }
}

function gpaColor(gpa: number): string {
  if (gpa >= 3.8) return 'text-emerald-400'
  if (gpa >= 3.5) return 'text-green-400'
  if (gpa >= 3.0) return 'text-emerald-300'
  if (gpa >= 2.5) return 'text-amber-400'
  return 'text-red-400'
}

export default function TimelineView({ profile, expandAll = false }: TimelineViewProps) {
  const smoothScrollState = useRef(new Map<HTMLDivElement, { target: number; rafId: number | null }>())

  useEffect(() => {
    const states = smoothScrollState.current
    return () => {
      states.forEach(state => {
        if (state.rafId !== null) {
          window.cancelAnimationFrame(state.rafId)
        }
      })
    }
  }, [])

  function animateToTarget(container: HTMLDivElement) {
    const states = smoothScrollState.current
    const state = states.get(container)
    if (!state) return

    const step = () => {
      const delta = state.target - container.scrollLeft
      if (Math.abs(delta) < 0.5) {
        container.scrollLeft = state.target
        state.rafId = null
        return
      }

      // Eased movement for smoother horizontal scrolling.
      container.scrollLeft += delta * 0.2
      state.rafId = window.requestAnimationFrame(step)
    }

    state.rafId = window.requestAnimationFrame(step)
  }

  function handleTimelineWheel(e: WheelEvent<HTMLDivElement>) {
    // Keep wheel interactions scoped to the timeline while hovered.
    e.preventDefault()
    e.stopPropagation()

    // Map vertical wheel motion to horizontal timeline movement.
    const horizontalDelta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
    const container = e.currentTarget
    const states = smoothScrollState.current
    const maxScroll = container.scrollWidth - container.clientWidth

    const existing = states.get(container)
    const nextTarget = Math.max(
      0,
      Math.min(maxScroll, (existing?.target ?? container.scrollLeft) + horizontalDelta),
    )

    if (!existing) {
      states.set(container, { target: nextTarget, rafId: null })
      animateToTarget(container)
      return
    }

    existing.target = nextTarget
    if (existing.rafId === null) {
      animateToTarget(container)
    }
  }

  // Use semesters from profile if available, otherwise group by semester from flat courses list
  const semesters: Semester[] = profile.semesters || []

  // Sort semesters chronologically (newest last for left-to-right timeline)
  const sortedSemesters = [...semesters].sort((a, b) => {
    const [aTerm, aYear] = a.term.split(' ')
    const [bTerm, bYear] = b.term.split(' ')
    if (aYear !== bYear) return parseInt(aYear) - parseInt(bYear)
    const order: Record<string, number> = { 'Spring': 0, 'Fall': 1, 'Summer': 2 }
    const aKey = Object.keys(order).find(k => k.toLowerCase() === aTerm.toLowerCase()) ?? aTerm
    const bKey = Object.keys(order).find(k => k.toLowerCase() === bTerm.toLowerCase()) ?? bTerm
    return (order[aKey] ?? 0) - (order[bKey] ?? 0)
  })

  if (sortedSemesters.length === 0) {
    // Fallback: group flat courses list by semester
    const bySemester: Record<string, Course[]> = {}
    for (const c of profile.courses || []) {
      const sem = c.semester || 'Unknown'
      if (!bySemester[sem]) bySemester[sem] = []
      bySemester[sem].push(c)
    }
    const inferred = Object.entries(bySemester).map(([term, courses]) => ({ term, gpa: 0, courses }))
    inferred.sort((a, b) => {
      const [aTerm, aYear] = a.term.split(' ')
      const [bTerm, bYear] = b.term.split(' ')
      if (aYear !== bYear) return parseInt(aYear) - parseInt(bYear)
      const order: Record<string, number> = { 'Spring': 0, 'Fall': 1, 'Summer': 2 }
      const aKey = Object.keys(order).find(k => k.toLowerCase() === aTerm.toLowerCase()) ?? aTerm
      const bKey = Object.keys(order).find(k => k.toLowerCase() === bTerm.toLowerCase()) ?? bTerm
      return (order[aKey] ?? 0) - (order[bKey] ?? 0)
    })
    if (inferred.length > 0) {
      return (
        <div className="overflow-x-auto no-scrollbar overscroll-contain pb-4" onWheelCapture={handleTimelineWheel}>
          <div className="flex gap-6 min-w-max">
            {inferred.map((sem, i) => (
              <SemesterColumn
                key={i}
                semester={sem}
                showConnector={i < inferred.length - 1}
                expandAll={expandAll}
              />
            ))}
          </div>
        </div>
      )
    }
    return (
      <div className="text-sm text-center py-12" style={{ color: 'var(--text-muted)' }}>
        No semester data available.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto no-scrollbar overscroll-contain pb-4" onWheelCapture={handleTimelineWheel}>
      <div className="relative min-w-max">
        <div className="flex gap-6 items-start">
          {sortedSemesters.map((sem, i) => (
            <SemesterColumn
              key={i}
              semester={sem}
              showConnector={i < sortedSemesters.length - 1}
              expandAll={expandAll}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function SemesterColumn({
  semester,
  showConnector = false,
  expandAll = false,
}: {
  semester: Semester
  showConnector?: boolean
  expandAll?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const { term, gpa, courses } = semester
  const showAllCourses = expandAll || expanded

  // Parse term and year
  const parts = term.split(' ')
  const season = parts[0] || term
  const year = parts[1] || ''

  const totalCredits = courses.reduce((sum, c) => sum + (c.credits || 0), 0)

  return (
    <div className="flex flex-col items-center gap-0 w-[160px] shrink-0">
      {/* Season icon in circle */}
      <div className="relative z-10 flex flex-col items-center">
        {showConnector && (
          <div
            className="absolute top-5 left-[calc(50%+20px)] w-[144px] h-0.5 pointer-events-none"
            style={{ background: 'var(--glass-border-hot)' }}
            aria-hidden="true"
          />
        )}
        <div className="glass w-10 h-10 rounded-full border-2 flex items-center justify-center mb-2" style={{ borderColor: 'var(--accent)' }}>
          <SeasonIcon season={season} />
        </div>
        <div className="text-center">
          <p className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{season}</p>
          <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{year}</p>
        </div>
      </div>

      {/* Semester GPA */}
      <div className="mt-1 mb-3">
        <span className={`text-sm font-bold font-mono ${gpa > 0 ? gpaColor(gpa) : ''}`} style={gpa <= 0 ? { color: 'var(--text-muted)' } : undefined}>
          {gpa > 0 ? gpa.toFixed(2) : '—'}
        </span>
      </div>

      {/* Course cards */}
      <div className="flex flex-col gap-2 w-full">
        {courses.slice(0, showAllCourses ? undefined : 3).map((c, i) => (
          <CourseCard key={i} course={c} />
        ))}
        {courses.length > 3 && !expandAll && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-center py-1 transition-colors"
            style={{ color: 'var(--accent)' }}
          >
            {expanded ? 'Show less' : `+${courses.length - 3} more`}
          </button>
        )}
      </div>

      {/* Credits total */}
      <div className="mt-3 text-xs text-center" style={{ color: 'var(--text-muted)' }}>
        {totalCredits} credits
      </div>
    </div>
  )
}

function CourseCard({ course }: { course: Course }) {
  const { id, title, credits, grade } = course

  return (
    <div className="glass rounded-2xl px-3 py-2 w-full interactive-lift" style={{ borderColor: 'var(--glass-border)' }}>
      <div className="flex items-start justify-between gap-1">
        <div className="flex-1 min-w-0">
          <p className="font-mono text-xs font-medium truncate" style={{ color: 'var(--accent)' }}>{id}</p>
          <p className="text-xs leading-tight mt-0.5 line-clamp-2" style={{ color: 'var(--text-primary)' }}>{title}</p>
        </div>
        <div className="flex flex-col items-end gap-0.5 shrink-0 ml-1">
          <span className={`text-xs font-bold ${gradeColor(grade)}`}>{grade}</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{credits}cr</span>
        </div>
      </div>
    </div>
  )
}
