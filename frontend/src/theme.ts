import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const KEY = 'demo-theme'

// The first visit follows the computer's setting; after a click, the choice is kept.
function initial(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark') return v
  } catch {
    /* storage blocked */
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(initial)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const setTheme = (t: Theme) => {
    setThemeState(t)
    try {
      localStorage.setItem(KEY, t)
    } catch {
      /* storage blocked: the choice lasts for this visit */
    }
  }

  return { theme, setTheme }
}
