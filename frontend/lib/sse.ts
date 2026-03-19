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

export async function startLesson(
  onChunk: (chunk: SSEChunk) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/lesson/start', { method: 'POST', signal })
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
