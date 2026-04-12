import { createContext, useContext, useState, useEffect, useRef } from 'react'
import { SCHEMES } from './schemes'

interface ThemeContextType {
  scheme: string
  setScheme: (id: string) => void
}

const ThemeContext = createContext<ThemeContextType>({
  scheme: 'dark',
  setScheme: () => {},
})

const STORAGE_KEY = 'gradYOU8_theme'

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [scheme, setSchemeState] = useState<string>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    // Migrate anyone still on parchment to dark
    if (!saved || saved === 'parchment') return 'dark'
    return saved
  })
  const isFirstRun = useRef(true)

  useEffect(() => {
    const vars = SCHEMES[scheme] || SCHEMES['dark']

    // Apply all CSS custom properties to :root
    const root = document.documentElement
    for (const [name, value] of Object.entries(vars)) {
      // Skip internal keys
      if (name.startsWith('_')) continue
      root.style.setProperty(name, value)
    }

    // Apply body background via inline style (gradient strings can't use CSS vars)
    const bodyBg = vars._bodyBg
    if (bodyBg) {
      document.body.style.background = bodyBg
    }

    // Set data-theme attribute on <html>
    document.documentElement.setAttribute('data-theme', scheme)

    // color-scheme: tells native controls (scrollbars, inputs) to adapt
    const isLight = scheme === 'light'
    document.documentElement.style.colorScheme = isLight ? 'light' : 'dark'

    // Persist to localStorage (skip on first run — already read from it)
    if (isFirstRun.current) {
      isFirstRun.current = false
      return
    }
    localStorage.setItem(STORAGE_KEY, scheme)
  }, [scheme])

  return (
    <ThemeContext.Provider value={{ scheme, setScheme: setSchemeState }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  return useContext(ThemeContext)
}
