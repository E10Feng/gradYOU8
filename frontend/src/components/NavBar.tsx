import { Link, useLocation } from 'react-router-dom'

export default function NavBar() {
  const location = useLocation()
  const isActive = (path: string) => location.pathname === path

  return (
    <nav className="glass-strong border-b px-6 py-4 flex items-center justify-between" style={{ borderBottomColor: 'var(--glass-border-mid)' }}>
      <div className="flex items-center gap-8">
        <Link to="/" className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)', fontFamily: "'Fraunces', serif", fontStyle: 'italic' }}>
          WashU Navigator
        </Link>
        <div className="flex gap-6 text-sm">
          <Link
            to="/"
            className={`transition-colors ${isActive('/') ? 'nav-active-dot' : ''}`}
            style={{ color: isActive('/') ? 'var(--text-primary)' : 'var(--text-muted)' }}
          >
            Audit
          </Link>
          <Link
            to="/courses"
            className={`transition-colors ${isActive('/courses') ? 'nav-active-dot' : ''}`}
            style={{ color: isActive('/courses') ? 'var(--text-primary)' : 'var(--text-muted)' }}
          >
            Courses
          </Link>
        </div>
      </div>
      <span className="text-xs hidden sm:inline" style={{ color: 'var(--text-subtle)' }}>WashU Graduation Navigator</span>
    </nav>
  )
}
