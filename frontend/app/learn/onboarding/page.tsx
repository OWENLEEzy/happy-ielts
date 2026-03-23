'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { sendGeneralOnboardingMessage } from '@/lib/sse'

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface LearningMapPreview {
  goal_profile: Record<string, unknown>
  learning_map: Record<string, unknown>
}

export default function GeneralOnboardingPage() {
  const router = useRouter()
  const [projectId, setProjectId] = useState<number | null>(null)
  const [topic, setTopic] = useState('')
  const [started, setStarted] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [preview, setPreview] = useState<LearningMapPreview | null>(null)
  const [confirming, setConfirming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const msgIdRef = useRef(0)
  const mkMsg = (role: Message['role'], content: string): Message => ({
    id: ++msgIdRef.current,
    role,
    content,
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startOnboarding = async () => {
    if (!topic.trim()) return
    const res = await fetch('/api/learn/onboarding/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic.trim(), tier: 'free' }),
    })
    if (!res.ok) return
    const data = await res.json()
    setProjectId(data.project_id)
    setStarted(true)
    setMessages([
      mkMsg(
        'assistant',
        `你好！我会帮你规划关于「${topic}」的学习课程。先告诉我，你学习它最想实现什么目标？`,
      ),
    ])
  }

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming || !projectId) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, mkMsg('user', userMsg)])
    setIsStreaming(true)

    let assistantMsg = ''
    setMessages((prev) => [...prev, mkMsg('assistant', '')])

    abortRef.current = new AbortController()
    try {
      await sendGeneralOnboardingMessage(
        projectId,
        userMsg,
        (token) => {
          assistantMsg += token
          setMessages((prev) => {
            const next = [...prev]
            next[next.length - 1] = { ...next[next.length - 1], content: assistantMsg }
            return next
          })
        },
        abortRef.current.signal,
      )

      // After agent saves goal profile, poll project status for draft map
      const projRes = await fetch(`/api/learn/projects/${projectId}`)
      if (projRes.ok) {
        const proj = await projRes.json()
        if (proj.goal_profile && proj.learning_map) {
          setPreview({ goal_profile: proj.goal_profile, learning_map: proj.learning_map })
        }
      }
    } catch {
      // aborted or error
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, projectId])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const confirmPlan = async () => {
    if (!projectId || !preview) return
    setConfirming(true)
    const res = await fetch('/api/learn/onboarding/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        goal_profile: preview.goal_profile,
        learning_map: preview.learning_map,
      }),
    })
    if (res.ok) {
      router.push(`/learn/preparing/${projectId}`)
    } else {
      setConfirming(false)
    }
  }

  if (!started) {
    return (
      <main
        className="min-h-screen flex flex-col items-center justify-center px-4"
        style={{ background: '#0f0d1a', color: '#e8e0d0' }}
      >
        <h1
          className="text-4xl mb-2 font-semibold"
          style={{ fontFamily: 'Cormorant Garamond, serif', color: '#c9a84c' }}
        >
          Scholar&apos;s Atelier
        </h1>
        <p className="text-sm mb-10 opacity-60">告诉我你想学什么，我来帮你规划</p>
        <div className="w-full max-w-md flex flex-col gap-4">
          <input
            className="w-full rounded-lg px-4 py-3 text-base outline-none"
            style={{ background: '#1a1730', border: '1px solid #2e2850', color: '#e8e0d0' }}
            placeholder="例如：吉他、量化交易、日语、烘焙..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && startOnboarding()}
            autoFocus
          />
          <button
            className="w-full py-3 rounded-lg font-medium transition-opacity"
            style={{ background: '#c9a84c', color: '#0f0d1a' }}
            onClick={startOnboarding}
            disabled={!topic.trim()}
          >
            开始规划
          </button>
        </div>
      </main>
    )
  }

  return (
    <main
      className="min-h-screen flex flex-col"
      style={{ background: '#0f0d1a', color: '#e8e0d0' }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-6 py-4 border-b"
        style={{ borderColor: '#2e2850' }}
      >
        <span
          className="text-lg font-semibold"
          style={{ fontFamily: 'Cormorant Garamond, serif', color: '#c9a84c' }}
        >
          学习规划
        </span>
        <span className="text-sm opacity-50">·</span>
        <span className="text-sm opacity-60">{topic}</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4 max-w-2xl w-full mx-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className="rounded-2xl px-4 py-3 max-w-[80%] text-sm leading-relaxed whitespace-pre-wrap"
              style={
                msg.role === 'user'
                  ? { background: '#c9a84c', color: '#0f0d1a' }
                  : { background: '#1a1730', color: '#e8e0d0', border: '1px solid #2e2850' }
              }
            >
              {msg.content}
              {msg.role === 'assistant' &&
                isStreaming &&
                msg.id === messages[messages.length - 1]?.id && (
                  <span className="animate-pulse ml-1 opacity-60">▋</span>
                )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Learning map preview */}
      {preview && (
        <div className="px-4 pb-4 max-w-2xl w-full mx-auto">
          <div
            className="rounded-xl p-4 text-sm"
            style={{ background: '#1a1730', border: '1px solid #c9a84c33' }}
          >
            <p className="font-medium mb-2" style={{ color: '#c9a84c' }}>
              📋 学习计划草稿
            </p>
            <pre className="opacity-70 text-xs overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(preview.learning_map, null, 2)}
            </pre>
            <button
              className="mt-3 w-full py-2 rounded-lg font-medium transition-opacity"
              style={{ background: '#c9a84c', color: '#0f0d1a' }}
              onClick={confirmPlan}
              disabled={confirming}
            >
              {confirming ? '正在准备课程...' : '确认计划，开始备课'}
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      {!preview && (
        <div className="px-4 pb-6 pt-2 max-w-2xl w-full mx-auto flex gap-2">
          <textarea
            className="flex-1 rounded-xl px-4 py-3 text-sm resize-none outline-none"
            style={{
              background: '#1a1730',
              border: '1px solid #2e2850',
              color: '#e8e0d0',
              minHeight: 48,
            }}
            rows={1}
            placeholder="回复顾问..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            className="px-4 py-2 rounded-xl font-medium transition-opacity disabled:opacity-40"
            style={{ background: '#c9a84c', color: '#0f0d1a' }}
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
          >
            发送
          </button>
        </div>
      )}
    </main>
  )
}
