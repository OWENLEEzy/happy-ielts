'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { client } from '@/lib/client'
import type { components } from '@/types/api'
import { sendGeneralOnboardingMessage } from '@/lib/sse'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL, glBtn, glBtnDisabled } from '@/lib/learn-theme'

type StartReq = components['schemas']['GeneralOnboardingStartRequest']
type ConfirmReq = components['schemas']['GeneralOnboardingConfirmRequest']

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
      <div className="min-h-screen flex flex-col" style={{ background: GL.bg, color: GL.fg }}>
        <Header dark />
        <main className="flex-1 flex flex-col items-center justify-center px-6">
          {/* Ambient glow */}
          <div
            className="pointer-events-none fixed top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(201,168,76,0.06) 0%, transparent 70%)',
              filter: 'blur(40px)',
            }}
          />

          <div className="relative z-10 w-full max-w-md text-center space-y-8">
            <div className="space-y-3">
              <div
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-mono-dm tracking-widest uppercase"
                style={{
                  borderColor: 'rgba(201,168,76,0.3)',
                  color: GL.amber,
                  background: 'rgba(201,168,76,0.06)',
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: GL.amber }} />
                学习规划
              </div>
              <h1
                className="font-cormorant font-light leading-tight"
                style={{ fontSize: 'clamp(2.8rem, 7vw, 4rem)', color: GL.fg }}
              >
                Scholar&apos;s
                <br />
                <em style={{ color: GL.amber, fontStyle: 'italic' }}>Atelier</em>
              </h1>
              <p
                className="text-sm leading-relaxed"
                style={{ color: GL.fgMuted, fontFamily: 'Manrope, sans-serif' }}
              >
                告诉我你想学什么，AI 老师为你深度备课
              </p>
            </div>

            <div className="flex flex-col gap-3">
              <input
                className="w-full rounded-xl px-5 py-4 text-base outline-none transition-all"
                style={{
                  background: GL.inputBg,
                  border: `1px solid ${GL.inputBorder}`,
                  color: GL.fg,
                  fontFamily: 'Manrope, sans-serif',
                }}
                placeholder="例如：吉他、量化交易、日语、烘焙..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && startOnboarding()}
                autoFocus
              />
              <button
                className="w-full py-4 rounded-xl font-medium transition-all disabled:opacity-40"
                style={
                  topic.trim()
                    ? {
                        ...glBtn,
                        boxShadow: '0 0 32px rgba(201,168,76,0.25), 0 4px 16px rgba(0,0,0,0.4)',
                      }
                    : glBtnDisabled
                }
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
    <div className="min-h-screen flex flex-col" style={{ background: GL.bg, color: GL.fg }}>
      <Header dark />

      {/* Topic bar */}
      <div
        className="flex items-center gap-3 px-6 py-3 border-b"
        style={{ borderColor: GL.navBorder }}
      >
        <span
          className="text-xs font-mono-dm tracking-widest uppercase"
          style={{ color: GL.amber }}
        >
          学习规划
        </span>
        <span className="text-xs opacity-30">·</span>
        <span className="text-sm opacity-60" style={{ fontFamily: 'Manrope, sans-serif' }}>
          {topic}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 flex flex-col gap-4 max-w-2xl w-full mx-auto">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div
                className="w-6 h-6 rounded-full flex-shrink-0 mr-2 mt-1 flex items-center justify-center text-xs"
                style={{
                  background: 'rgba(201,168,76,0.15)',
                  border: `1px solid ${GL.cardBorder}`,
                  color: GL.amber,
                }}
              >
                ✦
              </div>
            )}
            <div
              className="rounded-2xl px-4 py-3 max-w-[80%] text-sm leading-relaxed whitespace-pre-wrap"
              style={
                msg.role === 'user'
                  ? {
                      background: `linear-gradient(135deg, ${GL.amber}, #e8c96a)`,
                      color: '#0f0d1a',
                      fontFamily: 'Manrope, sans-serif',
                      fontWeight: 500,
                    }
                  : {
                      background: GL.card,
                      border: `1px solid ${GL.cardBorder}`,
                      color: GL.fg,
                      fontFamily: 'Manrope, sans-serif',
                    }
              }
            >
              {msg.content}
              {msg.role === 'assistant' &&
                isStreaming &&
                msg.id === messages[messages.length - 1]?.id && (
                  <span className="animate-pulse ml-1" style={{ color: GL.amber }}>
                    ▋
                  </span>
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
            className="rounded-2xl p-5"
            style={{ background: GL.card, border: `1px solid rgba(201,168,76,0.25)` }}
          >
            <div className="flex items-center gap-2 mb-3">
              <span
                className="text-xs font-mono-dm tracking-widest uppercase"
                style={{ color: GL.amber }}
              >
                学习计划草稿
              </span>
            </div>
            <pre
              className="text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap"
              style={{ color: 'rgba(240,235,224,0.6)', fontFamily: 'DM Mono, monospace' }}
            >
              {JSON.stringify(preview.learning_map, null, 2)}
            </pre>
            <button
              className="mt-4 w-full py-3 rounded-xl font-medium transition-all disabled:opacity-40"
              style={glBtn}
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
            className="flex-1 rounded-xl px-4 py-3 text-sm resize-none outline-none transition-all"
            style={{
              background: GL.inputBg,
              border: `1px solid ${GL.inputBorder}`,
              color: GL.fg,
              minHeight: 48,
              fontFamily: 'Manrope, sans-serif',
            }}
            rows={1}
            placeholder="回复顾问..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
          />
          <button
            className="px-4 py-2 rounded-xl font-medium transition-all disabled:opacity-30"
            style={input.trim() ? glBtn : glBtnDisabled}
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
