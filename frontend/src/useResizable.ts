import { useCallback, useRef, useState } from 'react'

function saveWidth(key: string, w: number) {
  try {
    localStorage.setItem(key, String(w))
  } catch {
    /* storage blocked: the width lasts for this visit */
  }
}

// A panel width the user drags with a handle, kept between visits.
export function useResizable(key: string, initialWidth: number, min: number, max: number) {
  const read = () => {
    try {
      const v = Number(localStorage.getItem(key))
      return v >= min && v <= max ? v : initialWidth
    } catch {
      return initialWidth
    }
  }
  const [width, setWidth] = useState(read)
  const latest = useRef(width)

  // side: which way the panel grows when the pointer moves right (+1 for a left panel, -1 for a right one).
  const startDrag = useCallback(
    (side: 1 | -1) => (e: React.PointerEvent) => {
      e.preventDefault()
      const startX = e.clientX
      const startW = latest.current
      const move = (ev: PointerEvent) => {
        const w = Math.min(max, Math.max(min, startW + side * (ev.clientX - startX)))
        latest.current = w
        setWidth(w)
      }
      const up = () => {
        window.removeEventListener('pointermove', move)
        window.removeEventListener('pointerup', up)
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
        saveWidth(key, latest.current)
      }
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
    },
    [key, min, max],
  )

  const reset = () => {
    latest.current = initialWidth
    setWidth(initialWidth)
    saveWidth(key, initialWidth)
  }

  return { width, startDrag, reset }
}
