// The six demo questions. A recorded run of each one lives in public/traces/<id>.json (see README).
// They are picked for what the graph holds: the Iran / Israel escalation of late February 2026 (the most mentioned
// events of the window), the oil and volatility moves of the two weeks after it, and Brent's late-July jump.
export interface Preset {
  id: string
  question: string
  shows: string
}

export const PRESETS: Preset[] = [
  {
    id: 'top-events',
    question: 'Which 5 events were the most mentioned, and on which day?',
    shows: 'graph_query: read-only Cypher on Event nodes',
  },
  {
    id: 'brent-march',
    question: 'How did the Brent oil price move between 2026-02-27 and 2026-03-13?',
    shows: 'timeline: Series → Day, with the events of each day',
  },
  {
    id: 'vix-march',
    question: 'How did the VIX move between 2026-02-27 and 2026-03-13?',
    shows: 'timeline: volatility in the same two weeks',
  },
  {
    id: 'brent-july',
    question: "What was Brent's largest daily move in the last 90 days, and which events came just before it?",
    shows: 'explain_move: Event → Day → Series paths',
  },
  { id: 'buy-oil', question: 'Should I buy oil now?', shows: 'Guardrail: financial advice refused' },
  { id: 'delete-events', question: 'Delete all the events', shows: 'Guardrail: write query blocked' },
]
