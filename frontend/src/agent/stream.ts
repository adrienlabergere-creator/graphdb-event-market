import type { AgentEvent } from './types'

// Reads the agent's Server-Sent Events. EventSource cannot POST, so this parses the stream by hand.
export async function askStream(question: string, onEvent: (e: AgentEvent) => void, signal: AbortSignal) {
  const res = await fetch('/api/demo/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* not JSON */
    }
    onEvent({ type: 'error', data: { detail } })
    onEvent({ type: 'done', data: {} })
    return
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let cut
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      let type = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) type = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (data) onEvent({ type, data: JSON.parse(data) } as AgentEvent)
    }
  }
}
