import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Chat from './pages/Chat'
import Audit from './pages/Audit'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-white">
        <nav className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="text-xl font-bold tracking-tight">
              WashU Navigator
            </Link>
            <div className="flex gap-6 text-sm text-slate-400">
              <Link to="/" className="hover:text-white transition">Chat</Link>
              <Link to="/audit" className="hover:text-white transition">Audit</Link>
            </div>
          </div>
          <span className="text-xs text-slate-600">Built with vectorless RAG + Gemini</span>
        </nav>

        <main className="max-w-5xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/audit" element={<Audit />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
