import { useState } from 'react'
import { StudentProfile, Semester, Course } from './TranscriptUpload'

interface TimelineViewProps {
  profile: StudentProfile
  expandAll?: boolean
}

function SeasonIcon({ season }: { season: string }) {
  const color =
    season === 'Fall' ? 'var(--accent-red)' :
    season === 'Spring' ? 'var(--accent-emerald)' :
    season === 'Summer' ? 'var(--accent-emerald)' :
    season === 'Winter' ? 'var(--text-muted)' :
    'var(--accent-emerald)'
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true" style={{ color }}>
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M8 3.5v3M16 3.5v3M4 9.5h16" />
    </svg>
  )
}

function gradeColor(grade: string): string {
  if (!grade || grade === 'CR' || grade === 'P') return 'var(--text-muted)'
  const g = grade.replace('+', '').replace('-', '').replace('CR', '').replace('P', '').trim()
  switch (g) {
    case 'A': return 'var(--accent-emerald)'
    case 'B': return 'var(--accent-emerald)'
    case 'C': return 'var(--accent-amber)'
    case 'D': return 'var(--accent)'
    case 'F': return 'var(--accent-red)'
    default: return 'var(--text-muted)'
  }
}

function gpaColor(gpa: number): string {
  if (gpa >= 3.8) return 'var(--accent-emerald)'
  if (gpa >= 3.5) return 'var(--accent-emerald)'
  if (gpa >= 3.0) return 'var(--accent-emerald)'
  if (gpa >= 2.5) return 'var(--accent-amber)'
  return 'var(--accent-red)'
}

export default function TimelineView({ profile, expandAll = false }: TimelineViewProps) {
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
        <div className="overflow-x-auto no-scrollbar pb-4">
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
    <div className="overflow-x-auto no-scrollbar pb-4">
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
        <span className="text-sm font-bold font-mono" style={gpa > 0 ? { color: gpaColor(gpa) } : { color: 'var(--text-muted)' }}>
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
  const [expanded, setExpanded] = useState(false)

  return (
    <button
      type="button"
      onClick={() => setExpanded(prev => !prev)}
      className="glass rounded-2xl px-3 py-2 w-full interactive-lift text-left"
      style={{ borderColor: 'var(--glass-border)' }}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="flex-1 min-w-0">
          <p className="font-mono text-xs font-medium truncate" style={{ color: 'var(--accent)' }}>{id}</p>
          <p
            className={`text-xs leading-tight mt-0.5 ${expanded ? 'break-words' : 'line-clamp-2'}`}
            style={{ color: 'var(--text-primary)' }}
          >
            {title}
          </p>
        </div>
        <div className="flex flex-col items-end gap-0.5 shrink-0 ml-1">
          <span className="text-xs font-bold" style={{ color: gradeColor(grade) }}>{grade}</span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{credits}cr</span>
        </div>
      </div>
    </button>
  )
}
