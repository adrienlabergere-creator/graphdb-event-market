import type { ApiEdge, ApiNode } from '../types'

// Server-Sent Events of POST /api/demo/ask/stream (app/routers/demo.py).

export interface PlanData {
  step: number
  tool: string // a tool name, or "finish"
  arguments: Record<string, unknown>
  warnings: string[]
}

export interface ToolData {
  step: number
  tool: string
  arguments: Record<string, unknown>
  duration_ms: number
  ok: boolean
  error: string | null
  summary: string
  cypher: string[]
  result: unknown
  nodes: ApiNode[]
  edges: ApiEdge[]
  hops: ApiEdge[]
}

export interface AnswerData {
  answer: string
  status: 'verified' | 'hypothesis'
  confidence: number
  tool_calls: { name: string; arguments: Record<string, unknown>; duration_ms: number }[]
  graph_paths: string[][]
  cypher_used: string[]
  warnings: string[]
  disclaimer: string
}

export type AgentEvent =
  | { type: 'start'; data: { question: string } }
  | { type: 'parse'; data: { refused: boolean; warnings: string[] } }
  | { type: 'plan'; data: PlanData }
  | { type: 'tool'; data: ToolData }
  | { type: 'validate'; data: { warnings: string[] } }
  | { type: 'answer'; data: AnswerData }
  | { type: 'error'; data: { detail: string } }
  | { type: 'done'; data: Record<string, never> }

// One event as recorded: `t` is the time in ms since the question was sent.
export type TimedEvent = AgentEvent & { t: number }

export interface Trace {
  question: string
  recorded_at: string
  events: TimedEvent[]
}
