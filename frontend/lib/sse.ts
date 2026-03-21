import type { SSEChunk, LessonAction } from '@/types'

export async function sendAction(
  action: LessonAction,
  onChunk: (chunk: SSEChunk) => void,
): Promise<void> {
  const res = await fetch('/api/lesson/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  })

  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          onChunk(JSON.parse(line.slice(6)))
        } catch {
          // skip malformed chunk
        }
      }
    }
  }
}

/** Map LangGraph node names to synthetic SSE chunks so the UI can restore phase on refresh. */
const NODE_TO_CHUNK: Record<string, SSEChunk> = {
  spaced_review: {
    type: 'awaiting_action',
    article_full_text: '',
    highlight_indices: [],
    user_level: 5,
  },
  reading: { type: 'awaiting_action', article_full_text: '', highlight_indices: [], user_level: 5 },
  writing_task: { type: 'writing_task', instruction: '', min_words: 50 },
  evaluate_writing: { type: 'writing_task', instruction: '', min_words: 50 },
}

export async function startLesson(
  onChunk: (chunk: SSEChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/lesson/start', { method: 'POST', signal })
  if (res.status === 409) {
    // Lesson already in progress — restore UI phase from checkpoint info
    try {
      const data = await res.json()
      const firstNode: string | undefined = (data.next as string[] | undefined)?.[0]
      const synthetic = firstNode ? NODE_TO_CHUNK[firstNode] : undefined
      if (synthetic) onChunk(synthetic)
    } catch {
      // If parsing fails, default to reading phase
      onChunk({
        type: 'awaiting_action',
        article_full_text: '',
        highlight_indices: [],
        user_level: 5,
      })
    }
    return
  }
  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          onChunk(JSON.parse(line.slice(6)))
        } catch {
          // skip
        }
      }
    }
  }
}

export async function sendOnboardingMessage(
  message: string,
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch('/api/onboarding/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  if (!res.ok) throw new Error(`API error: ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const lines = decoder.decode(value).split('\n')
    for (const line of lines) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          const chunk = JSON.parse(line.slice(6))
          if (chunk.type === 'token') onToken(chunk.content)
        } catch {
          // skip
        }
      }
    }
  }
}
