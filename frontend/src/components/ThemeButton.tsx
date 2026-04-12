import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useTheme } from '../themes/ThemeContext'
import { SCHEME_META } from '../themes/schemes'

export default function ThemeButton() {
  const { scheme, setScheme } = useTheme()
  const [open, setOpen] = useState(false)
  const [portalPos, setPortalPos] = useState<{ top: number; left: number } | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const meta = SCHEME_META[scheme] || SCHEME_META['dark']

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mouseup', handler)
    return () => document.removeEventListener('mouseup', handler)
  }, [open])

  // Compute portal position when dropdown opens
  useEffect(() => {
    if (!open) { setPortalPos(null); return }
    const rect = ref.current?.getBoundingClientRect()
    if (!rect) return
    setPortalPos({
      top: rect.bottom + 8,
      left: rect.left,
    })
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onMouseUp={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all"
        style={{
          background: 'var(--glass-bg)',
          border: '1px solid var(--glass-border-mid)',
          color: 'var(--text-muted)',
          backdropFilter: 'blur(12px)',
        }}
        title="Change color scheme"
      >
        <span
          className="w-3 h-3 rounded-full shrink-0"
          style={{ background: meta.swatch }}
        />
        <span>{meta.name}</span>
        <span style={{ fontSize: '8px', opacity: 0.7 }}>▾</span>
      </button>

      {open && portalPos && createPortal(
        <div
          onMouseUp={e => e.stopPropagation()}
          style={{
            position: 'fixed',
            top: portalPos.top,
            left: portalPos.left,
            zIndex: 9999,
            minWidth: 140,
            background: 'var(--glass-bg-ultra)',
            border: '1px solid var(--glass-border-mid)',
            backdropFilter: 'blur(32px)',
            boxShadow: 'var(--glass-shadow-lift)',
            borderRadius: '0.75rem',
            padding: '0.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          {Object.entries(SCHEME_META).map(([id, { name, swatch }]) => (
            <button
              key={id}
              onMouseUp={e => { e.stopPropagation(); setScheme(id); setOpen(false) }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.625rem',
                padding: '0.375rem 0.5rem',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                width: '100%',
                textAlign: 'left',
                background: scheme === id ? 'var(--glass-bg)' : 'transparent',
                border: `1px solid ${scheme === id ? 'var(--glass-border-hot)' : 'transparent'}`,
                color: scheme === id ? 'var(--text-primary)' : 'var(--text-muted)',
                transition: 'all 140ms',
              }}
              onMouseEnter={e => { if (scheme !== id) e.currentTarget.style.background = 'var(--glass-bg)' }}
              onMouseLeave={e => { if (scheme !== id) e.currentTarget.style.background = 'transparent' }}
            >
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  background: swatch,
                  flexShrink: 0,
                  border: '1px solid rgba(255,255,255,0.15)',
                }}
              />
              <span>{name}</span>
              {scheme === id && (
                <span style={{ marginLeft: 'auto', opacity: 0.6, fontSize: '9px' }}>✓</span>
              )}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}
