import { useState, useRef, DragEvent } from 'react'

export interface Course {
  id: string
  title: string
  credits: number
  grade: string
  semester: string
}

export interface Semester {
  term: string
  gpa: number
  courses: Course[]
}

export interface StudentProfile {
  student: { name: string; id: string; school: string }
  courses: Course[]
  gpa: number
  programs: Array<{ name: string; type: string; school?: string }>
  semesters?: Semester[]
}

interface Props {
  onProfileLoaded: (profile: StudentProfile) => void
}

export default function TranscriptUpload({ onProfileLoaded }: Props) {
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  async function upload(file: File) {
    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/upload-transcript', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Upload failed (${res.status})`)
      }

      const data = await res.json()
      // Persist to localStorage so Chat page can access the profile
      localStorage.setItem('gradYOU8_profile', JSON.stringify(data))
      onProfileLoaded(data as StudentProfile)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && file.name.toLowerCase().endsWith('.pdf')) {
      upload(file)
    } else {
      setError('Please drop a PDF file.')
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) upload(file)
  }

  function handleClick() {
    inputRef.current?.click()
  }

  return (
    <div className="flex flex-col gap-4">
      <div
        onClick={handleClick}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all
          ${dragging
            ? 'border-emerald-500 bg-emerald-500/10'
            : 'border-slate-600 hover:border-emerald-500 hover:bg-slate-800/50'
          }
          ${loading ? 'opacity-60 cursor-wait' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        {loading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-400 text-sm">Parsing transcript...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="text-4xl">📄</div>
            <div>
              <p className="text-white font-medium">Drop your transcript PDF here</p>
              <p className="text-slate-400 text-sm mt-1">or click to browse — PDF only</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3">
          <span className="text-red-400 text-sm">{error}</span>
        </div>
      )}
    </div>
  )
}
