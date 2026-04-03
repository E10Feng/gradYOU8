import { useState } from 'react'

interface Requirement {
  group: string
  description: string
  satisfied: boolean
  courses: string[]
}

export default function Audit() {
  const [courses, setCourses] = useState<{id: string; title: string; credits: number}[]>([])
  const [courseInput, setCourseInput] = useState('')
  const [program, setProgram] = useState('biology')
  const [results, setResults] = useState<{satisfied: string[]; missing: Requirement[]} | null>(null)

  function addCourse() {
    if (!courseInput.trim()) return
    const parts = courseInput.trim().split(/\s+/)
    const id = parts[0]?.toUpperCase() || courseInput
    const title = parts.slice(1).join(' ') || id
    setCourses(prev => [...prev, { id, title, credits: 3 }])
    setCourseInput('')
  }

  function removeCourse(id: string) {
    setCourses(prev => prev.filter(c => c.id !== id))
  }

  async function runAudit() {
    // TODO: Wire to /api/audit when backend is ready
    setResults({
      satisfied: courses.map(c => c.id),
      missing: [
        { group: 'Gateway Courses', description: 'BIO 296 + BIO 297', satisfied: false, courses: [] },
        { group: 'Upper-Level Electives', description: '4 courses at 3000+ level', satisfied: false, courses: [] },
      ]
    })
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">Graduation Audit</h1>
        <p className="text-slate-400 text-sm">
          Track which requirements you've satisfied and what's still missing.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Course tracker */}
        <div className="bg-slate-900 rounded-xl p-5 flex flex-col gap-4">
          <h2 className="font-semibold">Your Courses</h2>

          <div className="flex gap-2">
            <input
              type="text"
              value={courseInput}
              onChange={e => setCourseInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCourse())}
              placeholder="e.g., BIOL 296 Biochemistry I"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={addCourse}
              className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-sm transition"
            >
              Add
            </button>
          </div>

          {courses.length === 0 ? (
            <p className="text-slate-500 text-sm">No courses added yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {courses.map(c => (
                <li key={c.id} className="flex items-center justify-between bg-slate-800 rounded-lg px-3 py-2 text-sm">
                  <span className="font-mono text-indigo-300">{c.id}</span>
                  <span className="text-slate-400">{c.title}</span>
                  <button onClick={() => removeCourse(c.id)} className="text-slate-600 hover:text-red-400 text-xs">✕</button>
                </li>
              ))}
            </ul>
          )}

          <button
            onClick={runAudit}
            className="bg-emerald-600 hover:bg-emerald-700 text-white py-2.5 rounded-lg text-sm font-medium transition"
          >
            Run Audit
          </button>
        </div>

        {/* Requirements */}
        <div className="bg-slate-900 rounded-xl p-5 flex flex-col gap-4">
          <h2 className="font-semibold">Requirements — {program.toUpperCase()}</h2>
          <p className="text-slate-500 text-xs">Select your program above to load requirements.</p>

          {results ? (
            <div className="flex flex-col gap-3">
              {results.satisfied.length > 0 && (
                <div>
                  <p className="text-emerald-400 text-xs font-medium mb-2">SATISFIED</p>
                  {results.satisfied.map(s => (
                    <div key={s} className="text-sm text-slate-300 bg-slate-800 rounded px-3 py-1.5 mb-1 flex items-center gap-2">
                      <span className="text-emerald-400">✓</span> {s}
                    </div>
                  ))}
                </div>
              )}
              {results.missing.map((r, i) => (
                <div key={i}>
                  <p className="text-amber-400 text-xs font-medium mb-2">MISSING — {r.group}</p>
                  <div className="text-sm text-slate-300 bg-slate-800 rounded px-3 py-2 border border-amber-900">
                    <p>{r.description}</p>
                    <p className="text-slate-500 text-xs mt-1">Add courses to satisfy this requirement</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">Add courses and click "Run Audit" to see your progress.</p>
          )}
        </div>
      </div>
    </div>
  )
}
