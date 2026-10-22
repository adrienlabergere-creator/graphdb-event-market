import type { GNode } from '../types'

// "Timeline" layout: trading days are pinned on a horizontal time axis, the market sits above it,
// themes and countries below. Events are free: their links pull them between their day, theme and country.
const WIDTH = 1800
export const EVENT_BAND_Y = 165
const ROW = { Commodity: -470, Currency: -470, PriceSeries: -300, TradingDay: 0, Theme: 320, Country: 500 } as const

function spread(nodes: GNode[], y: number, width = WIDTH) {
  const step = width / (nodes.length + 1)
  nodes.forEach((n, i) => {
    n.fx = -width / 2 + step * (i + 1)
    n.fy = y
  })
}

export function applyTimelineLayout(nodes: GNode[]) {
  const by = (label: string) => nodes.filter((n) => n.label === label).sort((a, b) => a.key.localeCompare(b.key))
  spread(by('TradingDay'), ROW.TradingDay)
  spread(by('PriceSeries'), ROW.PriceSeries, WIDTH * 0.7)
  spread([...by('Commodity'), ...by('Currency')], ROW.Commodity, WIDTH * 0.5)
  spread(by('Theme'), ROW.Theme, WIDTH * 0.8)
  spread(by('Country'), ROW.Country)
}

// Where a newly found event should appear: under its day, between the time axis and the themes.
export function seedEventPosition(event: GNode, day?: GNode) {
  if (event.x !== undefined) return
  event.x = (day?.fx ?? 0) + (Math.random() - 0.5) * 40
  event.y = EVENT_BAND_Y + (Math.random() - 0.5) * 60
}
