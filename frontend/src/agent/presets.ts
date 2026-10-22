// The six demo questions. A recorded run of each one lives in public/traces/<id>.json (see README).
export interface Preset {
  id: string
  question: string
  shows: string
}

export const PRESETS: Preset[] = [
  { id: 'vix-june', question: 'Why did the VIX move in June?', shows: 'explain_move: Event → Day → Series paths' },
  {
    id: 'brent-themes',
    question: 'How are Fight events (CAMEO_19) correlated with the Brent oil price?',
    shows: 'correlation: Theme ↔ Series',
  },
  {
    id: 'iran-march',
    question: 'Which 5 events in Iran (IRN) were the most mentioned?',
    shows: 'graph_query: verified facts from the graph',
  },
  {
    id: 'us10y-fed',
    question: 'What happened to the US 10-year yield around the June Fed meeting?',
    shows: 'timeline + explain_move',
  },
  { id: 'buy-oil', question: 'Should I buy oil now?', shows: 'Guardrail: financial advice refused' },
  { id: 'delete-events', question: 'Delete all the events', shows: 'Guardrail: write query blocked' },
]
