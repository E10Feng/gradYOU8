import { useState } from 'react'
import TranscriptUpload, { StudentProfile } from '../components/TranscriptUpload'
import AuditDashboard from '../components/AuditDashboard'

export default function Audit() {
  const [profile, setProfile] = useState<StudentProfile | null>(null)

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Degree Audit</h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Upload your transcript to see how your courses count toward your degree requirements.
        </p>
      </div>

      {/* Upload section */}
      <TranscriptUpload onProfileLoaded={setProfile} />

      {/* Audit dashboard — shown only after profile is loaded */}
      {profile && (
        <AuditDashboard profile={profile} />
      )}

      {!profile && (
        <div className="flex flex-col items-center justify-center py-16" style={{ color: 'var(--text-muted)' }}>
          <div className="text-5xl mb-4">🎓</div>
          <p className="text-sm">Upload your transcript above to get started.</p>
        </div>
      )}
    </div>
  )
}
