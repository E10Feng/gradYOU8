import { Link, useLocation } from 'react-router-dom'

export default function NavBar() {
  const location = useLocation()
  const isActive = (path: string) => location.pathname === path

  return (
    <nav className="border-b border-slate-800 px-6 py-4 flex items-center justify-between bg-slate-950">
      <div className="flex items-center gap-8">
        <Link to="/" className="text-xl font-bold tracking-tight text-white">
          WashU Navigator
        </Link>
        <div className="flex gap-6 text-sm">
          <Link to="/" className={`hover:text-white transition ${isActive('/') ? 'text-white' : 'text-slate-400'}`}>Audit</Link>
          <Link to="/courses" className={`hover:text-white transition ${isActive('/courses') ? 'text-white' : 'text-slate-400'}`}>Courses</Link>
        </div>
      </div>
      <span className="text-xs text-slate-600">WashU Graduation Navigator</span>
    </nav>
  )
}
