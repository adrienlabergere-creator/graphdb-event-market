// The public build (VITE_STATIC=1, used on Vercel) has no backend at all: the graph comes from a snapshot file,
// the agent runs are the recorded ones, and nothing can call the API or the model.
export const STATIC = import.meta.env.VITE_STATIC === '1'

export const REPO_URL = 'https://github.com/adrienlabergere-creator/graphdb-event-market'
