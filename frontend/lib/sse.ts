import type { SSEChunk, LessonAction } from '@/types'
import type { components } from '@/types/api'

type LessonActionReq = components['schemas']['LessonActionRequest']
type OnboardingMsgReq = components['schemas']['OnboardingMessageRequest']
type GeneralOnboardingMsgReq = components['schemas']['GeneralOnboardingMessageRequest']

export async function sendAction(
  action: LessonAction,
  onChunk: (chunk: SSEChunk) => void,
): Promise<void> {
  // Validate action shape matches LessonActionRequest schema
  const body: LessonActionReq = action
  const res = await fetch('/api/lesson/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  await _readSSEChunks(res, (line) => {
    try {
      onChunk(JSON.parse(line))
    } catch {
      /* skip */
    }
  })
}

/** Map LangGraph node names to synthetic SSE chunks for UI phase restore. */
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
    try {
      const data = await res.json()
      if (data.interrupt) {
        onChunk(data.interrupt as SSEChunk)
        return
      }
      const firstNode: string | undefined = (data.next as string[] | undefined)?.[0]
      const synthetic = firstNode ? NODE_TO_CHUNK[firstNode] : undefined
      if (synthetic) onChunk(synthetic)
    } catch {
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
  await _readSSEChunks(res, (line) => {
    try {
      onChunk(JSON.parse(line))
    } catch {
      /* skip */
    }
  })
}

export async function sendGeneralOnboardingMessage(
  projectId: number,
  message: string,
  onToken: (token: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const body: GeneralOnboardingMsgReq = { project_id: projectId, message }
  const res = await fetch('/api/learn/onboarding/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) throw new Error('SSE failed')
  await _readSSEChunks(res, onToken)
}

export async function sendOnboardingMessage(
  message: string,
  onToken: (token: string) => void,
): Promise<void> {
  const body: OnboardingMsgReq = { message, thread_id: 'onboarding' }
  const res = await fetch('/api/onboarding/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  await _readSSEChunks(res, (line) => {
    try {
      const chunk = JSON.parse(line)
      if (chunk.type === 'token') onToken(chunk.content)
    } catch {
      /* skip */
    }
  })
}

// ── Private helper ──────────────────────────────────────────────────────────

async function _readSSEChunks(res: Response, onLine: (data: string) => void): Promise<void> {
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    for (const line of decoder.decode(value).split('\n')) {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        onLine(line.slice(6))
      }
    }
  }
}
