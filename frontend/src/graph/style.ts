import type { Resolved } from '../theme'
import type { ApiNode, Label } from '../types'

// Node colours, chosen to read on both the ivory and the charcoal background.
export const COLORS: Record<Label, string> = {
  Event: '#d97757',
  Country: '#6a9bcc',
  Theme: '#b77aa0',
  TradingDay: '#a8a59a',
  PriceSeries: '#5f9b6d',
  Commodity: '#c39a3c',
  Currency: '#4a9a96',
  Claim: '#c4566a',
}

// Everything else the canvas draws, per theme (the canvas cannot read CSS variables).
interface GraphPalette {
  background: string
  label: string
  labelDim: string
  link: string
  priceLink: string
  linkDim: string
  hot: string
  hotPast: string
  particle: string
  halo: string
  day: string
}

export const PALETTES: Record<Resolved, GraphPalette> = {
  light: {
    background: '#faf9f5',
    label: '#3d3d3a',
    labelDim: 'rgba(61,61,58,0.35)',
    link: 'rgba(20,20,19,0.10)',
    priceLink: 'rgba(95,155,109,0.10)',
    linkDim: 'rgba(20,20,19,0.035)',
    hot: '#4c5fd5',
    hotPast: 'rgba(76,95,213,0.45)',
    particle: '#1f2a8a',
    halo: '76,95,213',
    day: '#b9b6aa',
  },
  dark: {
    background: '#262624',
    label: '#d6d4cb',
    labelDim: 'rgba(214,212,203,0.3)',
    link: 'rgba(245,244,239,0.10)',
    priceLink: 'rgba(95,155,109,0.12)',
    linkDim: 'rgba(245,244,239,0.035)',
    hot: '#8c9bff',
    hotPast: 'rgba(140,155,255,0.45)',
    particle: '#e3e6ff',
    halo: '140,155,255',
    day: '#6b6a64',
  },
}

export const nodeColor = (n: ApiNode, palette: GraphPalette) => (n.label === 'TradingDay' ? palette.day : COLORS[n.label])

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
