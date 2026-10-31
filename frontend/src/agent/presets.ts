// The four demo questions. A recorded run of each one lives in public/traces/<id>.json (see README).
// They are picked for what the graph holds: the volatility move of the two weeks after the Iran / Israel strikes of
// late February 2026, and Brent's late-July jump.
export interface Preset {
  id: string
  question: string
  shows: string
}

export const PRESETS: Preset[] = [
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
