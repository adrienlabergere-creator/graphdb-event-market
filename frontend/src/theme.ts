import { useEffect, useState } from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'
export type Resolved = 'light' | 'dark'

const KEY = 'demo-theme'

function stored(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

const media = () => window.matchMedia('(prefers-color-scheme: dark)')

// Light / dark / follow the system. The choice sits on <html data-theme> so the CSS tokens switch with it.
export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(stored)
  const [systemDark, setSystemDark] = useState(() => media().matches)

  useEffect(() => {
    const m = media()
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    m.addEventListener('change', onChange)
    return () => m.removeEventListener('change', onChange)
  }, [])

  const resolved: Resolved = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice

  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', choice)
    try {
      localStorage.setItem(KEY, choice)
    } catch {
      /* storage blocked: the choice lasts for this visit */
    }
  }, [choice])

  return { choice, setChoice, resolved }
}
