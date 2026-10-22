import type { ApiNode, Label } from '../types'

export const COLORS: Record<Label, string> = {
  Event: '#f97316',
  Country: '#38bdf8',
  Theme: '#a78bfa',
  TradingDay: '#64748b',
  PriceSeries: '#22c55e',
  Commodity: '#eab308',
  Currency: '#14b8a6',
  Claim: '#f43f5e',
}

export const LEGEND: Label[] = ['Event', 'TradingDay', 'PriceSeries', 'Theme', 'Country', 'Commodity', 'Currency']

// Short name drawn on the axis rows (countries are too many for full names).
export function shortName(n: ApiNode): string {
  return n.label === 'Country' ? n.key : nodeName(n)
}

export function nodeName(n: ApiNode): string {
  const p = n.props
  switch (n.label) {
    case 'Event': {
      const title = String(p.title ?? n.key)
      return title.length > 48 ? `${title.slice(0, 45)}…` : title
    }
    case 'Country':
    case 'Commodity':
    case 'Currency':
      return String(p.name ?? n.key)
    case 'Theme':
      return String(p.label ?? n.key)
    default:
      return n.key
  }
}

export function nodeRadius(n: ApiNode): number {
  switch (n.label) {
    case 'PriceSeries': return 9
    case 'Theme': return 7
    case 'Commodity':
    case 'Currency': return 6
    case 'Country': return 5
    case 'TradingDay': return 2.5
    case 'Event': {
      const mentions = Number(n.props.num_mentions ?? 1)
      return 2 + Math.min(4, Math.log10(mentions + 1))
    }
    default: return 4
  }
}

// Labels always drawn (the others appear on hover, or when the agent touches them in step 4).
export function alwaysLabelled(n: ApiNode): boolean {
  if (n.label === 'TradingDay') return n.key.endsWith('-01') // first of each month: a time axis
  return n.label !== 'Event'
}
