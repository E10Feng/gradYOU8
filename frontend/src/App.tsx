import { ThemeProvider } from './themes/ThemeContext'
import Profile from './pages/Profile'
import PasswordGate from './components/PasswordGate'

export default function App() {
  return (
    <ThemeProvider>
      <PasswordGate>
        <div className="min-h-screen text-[color:var(--text-primary)]">
          <main className="max-w-[1600px] mx-auto px-6 py-8">
            <Profile />
          </main>
        </div>
      </PasswordGate>
    </ThemeProvider>
  )
}
