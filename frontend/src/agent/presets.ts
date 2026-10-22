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
    question: 'Which event theme is most correlated with Brent, and how strong is the correlation?',
    shows: 'correlation: Theme ↔ Series',
  },
  {
    id: 'iran-march',
    question: 'How many events took place in Iran (IRN) in March 2026?',
    shows: 'graph_query: a verified fact',
  },
  {
    id: 'us10y-fed',
    question: 'What happened to the US 10-year yield around the June Fed meeting?',
    shows: 'timeline + explain_move',
  },
  { id: 'buy-oil', question: 'Should I buy oil now?', shows: 'Guardrail: financial advice refused' },
  { id: 'delete-events', question: 'Delete all the events', shows: 'Guardrail: write query blocked' },
]
