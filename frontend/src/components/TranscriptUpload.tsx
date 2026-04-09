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
        className={`upload-zone p-10 text-center cursor-pointer${dragging ? ' dragging' : ''}${loading ? ' opacity-60 cursor-wait' : ''}`}
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
            <div className="w-8 h-8 spinner-green" />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Parsing transcript...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)' }} aria-hidden="true">
              <path d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            <div>
              <p className="font-medium" style={{ color: 'var(--text-primary)' }}>Drop your transcript PDF here</p>
              <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>or click to browse — PDF only</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="glass flex items-center gap-2 rounded-lg px-4 py-3" style={{ borderColor: 'rgba(201, 79, 79, 0.35)' }}>
          <span className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</span>
        </div>
      )}
    </div>
  )
}
