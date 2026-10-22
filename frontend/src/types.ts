// Shapes returned by /api/demo/* (see app/routers/demo.py).

export type Label =
  | 'Event' | 'Country' | 'Theme' | 'Commodity' | 'Currency' | 'PriceSeries' | 'TradingDay' | 'Claim'

export interface ApiNode {
  id: string // "Label:key"
  label: Label
  key: string
  props: Record<string, unknown>
}

export interface ApiEdge {
  source: string
  target: string
  type: string
  props: Record<string, unknown>
}

export interface GraphPayload {
  nodes: ApiNode[]
  edges: ApiEdge[]
}

// What the force graph holds. x/y/fx/fy are set by the layout and the simulation.
export interface GNode extends ApiNode {
  x?: number
  y?: number
  fx?: number
  fy?: number
}

export interface GLink {
  id: string // "source|type|target"
  source: string | GNode
  target: string | GNode
  type: string
  props: Record<string, unknown>
}
