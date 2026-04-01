'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { client } from '@/lib/client'
import type { components } from '@/types/api'
import { sendGeneralOnboardingMessage } from '@/lib/sse'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { DogAvatar } from '@/components/DogAvatar'

type StartReq = components['schemas']['GeneralOnboardingStartRequest']

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface LearningMapPreview {
  goal_profile: components['schemas']['UserGoalProfile']
  learning_map: components['schemas']['LearningMap-Output']
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
    const body: StartReq = { topic: topic.trim(), tier: 'free' }
    const { data, response } = await client.POST('/api/learn/projects', { body })
    if (!response.ok) return
    setProjectId(data?.project_id ?? null)
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

      const { data: proj } = await client.GET('/api/learn/projects/{project_id}', {
        params: { path: { project_id: projectId } },
      })
      if (proj?.goal_profile && proj.learning_map) {
        setPreview({ goal_profile: proj.goal_profile, learning_map: proj.learning_map })
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
    const { response: confirmRes } = await client.PATCH('/api/learn/projects/{project_id}', {
      params: { path: { project_id: projectId! } },
      body: { goal_profile: preview.goal_profile, learning_map: preview.learning_map },
    })
    if (confirmRes.ok) {
      localStorage.setItem('generalProjectId', String(projectId))
      router.push(`/learn/preparing/${projectId}`)
    } else {
      setConfirming(false)
    }
  }

  if (!started) {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex flex-col items-center justify-center px-6">
          <div className="relative z-10 w-full max-w-md space-y-8">
            {/* Professor 金毛 tip card */}
            <div className="bg-tertiary-container/25 border border-primary/10 rounded-lg p-4 flex items-center gap-3 mb-6">
              <DogAvatar
                role="teacher"
                size={36}
                emphasis="card"
                alt="Professor 金毛"
                seedKey="general-onboarding-intro"
              />
              <div>
                <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
                  Professor 金毛
                </div>
                <p className="text-xs text-on-surface-variant font-body">
                  告诉我你想学什么，我为你制定专属课程
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3">
              <input
                className="w-full rounded-lg border border-outline-variant/20 bg-surface-container-low px-5 py-4 text-base text-on-surface font-body focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
                placeholder="例如：吉他、量化交易、日语、烘焙..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && startOnboarding()}
                autoFocus
              />
              <button
                className="w-full signature-gradient text-white py-3.5 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                onClick={startOnboarding}
                disabled={!topic.trim()}
              >
                开始规划 →
              </button>
            </div>
          </div>
        </main>
        <MobileNav />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      {/* Topic bar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-outline-variant/20">
        <span className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
          学习规划
        </span>
        <span className="text-xs opacity-30">·</span>
        <span className="text-sm text-on-surface-variant font-body">{topic}</span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4 max-w-2xl w-full mx-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="mr-2 mt-1 flex-shrink-0">
                <DogAvatar
                  role="teacher"
                  size={28}
                  emphasis="inline"
                  alt="Professor 金毛"
                  seedKey="general-onboarding-message"
                />
              </div>
            )}
            <div
              className={`rounded-2xl px-4 py-3 max-w-[80%] text-sm leading-relaxed whitespace-pre-wrap font-body ${
                msg.role === 'user'
                  ? 'signature-gradient text-white rounded-br-sm'
                  : 'bg-surface-container-lowest border border-outline-variant/20 rounded-bl-sm text-on-surface'
              }`}
            >
              {msg.content}
              {msg.role === 'assistant' &&
                isStreaming &&
                msg.id === messages[messages.length - 1]?.id && (
                  <span className="animate-pulse ml-1 text-primary">▋</span>
                )}
            </div>
            {msg.role === 'user' && (
              <div className="ml-2 mt-1 flex-shrink-0">
                <DogAvatar
                  role="user"
                  size={28}
                  emphasis="inline"
                  alt="小白"
                />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Learning map preview */}
      {preview && (
        <div className="px-4 pb-4 max-w-2xl w-full mx-auto">
          <div className="bg-surface-container-lowest rounded-xl p-5 shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)]">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
                学习计划草稿
              </span>
            </div>
            <pre className="text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap text-on-surface-variant font-mono">
              {JSON.stringify(preview.learning_map, null, 2)}
            </pre>
            <button
              className="mt-4 w-full signature-gradient text-white py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-50"
              onClick={confirmPlan}
              disabled={confirming}
            >
              {confirming ? '正在准备课程...' : '确认计划，开始备课 →'}
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      {!preview && (
        <div className="px-4 pb-6 pt-2 max-w-2xl w-full mx-auto flex gap-2">
          <textarea
            className="flex-1 rounded-xl border border-outline-variant/20 bg-surface-container-low/60 px-4 py-3 text-sm font-body text-on-surface resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
            rows={1}
            placeholder="回复顾问..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            className="signature-gradient text-white px-4 py-2 rounded-xl font-bold text-sm font-label shadow shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-50"
            onClick={sendMessage}
            disabled={isStreaming || !input.trim()}
          >
            发送
          </button>
        </div>
      )}

      <MobileNav />
    </div>
  )
}
