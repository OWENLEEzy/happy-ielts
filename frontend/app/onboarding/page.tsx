'use client'
import { useState, useRef, useEffect } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { client } from '@/lib/client'
import type { components } from '@/types/api'
import { sendOnboardingMessage } from '@/lib/sse'
import { useOnboardingStatus } from '@/hooks/useLesson'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { getRandomTeacherDogUrl } from '@/lib/constants'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function OnboardingPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: '你好！我是你的语言学习顾问。先告诉我，你学英语最迫切想解决什么问题？',
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showPreferenceCards, setShowPreferenceCards] = useState(false)
  const [bandwidth, setBandwidth] = useState<number | null>(null)
  const [writingMode, setWritingMode] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { data: status, mutate } = useOnboardingStatus()
  const [dogUrls, setDogUrls] = useState<{
    intro: string
    message: string
    streaming: string
  } | null>(null)

  useEffect(() => {
    setDogUrls({
      intro: getRandomTeacherDogUrl(),
      message: getRandomTeacherDogUrl(),
      streaming: getRandomTeacherDogUrl(),
    })
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (status?.ready && !showPreferenceCards) {
      setShowPreferenceCards(true)
    }
  }, [status?.ready, showPreferenceCards])

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setIsStreaming(true)

    let assistantContent = ''
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

    try {
      await sendOnboardingMessage(userMsg, (token) => {
        assistantContent += token
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: assistantContent }
          return updated
        })
      })
      await mutate()
    } finally {
      setIsStreaming(false)
    }
  }

  const handlePreferenceSubmit = async () => {
    if (!bandwidth || !writingMode) return
    setSubmitting(true)
    type SavePrefsReq = components['schemas']['SavePreferencesRequest']
    try {
      const body: SavePrefsReq = {
        bandwidth_minutes: bandwidth,
        writing_mode: writingMode as SavePrefsReq['writing_mode'],
      }
      await client.POST('/api/onboarding/preferences', { body })
      await client.POST('/api/planner/run', {})
      router.push('/lesson')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-8 pb-[calc(var(--mobile-nav-height)+8px)] md:pb-8 flex flex-col gap-4 min-h-0">
        {/* Tutor intro card */}
        <div className="flex items-center gap-3 bg-tertiary-container/25 rounded-lg p-4 border border-primary/10">
          <div className="relative w-12 h-12 rounded-full overflow-hidden border-2 border-primary/20 flex-shrink-0">
            {dogUrls && (
              <Image src={dogUrls.intro} fill sizes="48px" className="object-cover" alt="顾问" />
            )}
          </div>
          <div>
            <div className="text-[11px] font-black text-primary uppercase tracking-wider font-label">
              Professor 金毛
            </div>
            <div className="text-xs text-on-surface-variant">你的专属语言学习顾问</div>
          </div>
        </div>

        {/* Message list */}
        <div className="flex-1 min-h-0 space-y-3 overflow-y-auto">
          {messages.map((m, i) => (
            <div
              key={`msg-${i}`}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="relative w-7 h-7 rounded-full overflow-hidden border border-primary/20 mr-2 flex-shrink-0 mt-1">
                  {dogUrls && (
                    <Image
                      src={dogUrls.message}
                      fill
                      sizes="28px"
                      className="object-cover"
                      alt=""
                    />
                  )}
                </div>
              )}
              <div
                className={`max-w-[80%] px-4 py-3 rounded-lg text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'signature-gradient text-white rounded-br-sm'
                    : 'bg-surface-container-lowest border border-outline-variant/20 text-on-surface rounded-bl-sm shadow-sm'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          {isStreaming && (
            <div className="flex justify-start">
              <div className="relative w-7 h-7 rounded-full overflow-hidden border border-primary/20 mr-2 flex-shrink-0 mt-1">
                {dogUrls && (
                  <Image
                    src={dogUrls.streaming}
                    fill
                    sizes="28px"
                    className="object-cover"
                    alt=""
                  />
                )}
              </div>
              <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3 flex gap-1.5 items-center">
                <span className="dot1 w-2 h-2 bg-primary rounded-full inline-block" />
                <span className="dot2 w-2 h-2 bg-primary rounded-full inline-block" />
                <span className="dot3 w-2 h-2 bg-primary rounded-full inline-block" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Preference cards (shown when agent asks for them) */}
        {showPreferenceCards && (
          <div className="space-y-4">
            {/* Bandwidth */}
            <div>
              <div className="text-xs font-black text-primary uppercase tracking-wider font-label mb-2">
                每日学习时长
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[15, 25, 40].map((mins) => (
                  <button
                    key={mins}
                    onClick={() => setBandwidth(mins)}
                    className={`py-3 rounded-lg font-bold text-sm font-label border-2 transition-all ${
                      bandwidth === mins
                        ? 'border-primary bg-primary text-white'
                        : 'border-outline-variant/30 text-on-surface hover:border-primary/50'
                    }`}
                  >
                    {mins} 分钟
                  </button>
                ))}
              </div>
            </div>
            {/* Writing mode */}
            <div>
              <div className="text-xs font-black text-primary uppercase tracking-wider font-label mb-2">
                写作目标
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { val: 'professional', label: '职场英语' },
                  { val: 'ielts_task1', label: '雅思 Task 1' },
                  { val: 'ielts_task2', label: '雅思 Task 2' },
                ].map((o) => (
                  <button
                    key={o.val}
                    onClick={() => setWritingMode(o.val)}
                    className={`py-3 rounded-lg font-bold text-sm font-label border-2 transition-all ${
                      writingMode === o.val
                        ? 'border-primary bg-primary text-white'
                        : 'border-outline-variant/30 text-on-surface hover:border-primary/50'
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            {bandwidth && writingMode && (
              <button
                onClick={handlePreferenceSubmit}
                disabled={!bandwidth || !writingMode || submitting}
                className="w-full signature-gradient text-white py-3 rounded-full font-bold font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-60 disabled:scale-100 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <span className="flex items-center justify-center gap-1.5">
                    <span className="dot1 w-2 h-2 bg-white rounded-full inline-block" />
                    <span className="dot2 w-2 h-2 bg-white rounded-full inline-block" />
                    <span className="dot3 w-2 h-2 bg-white rounded-full inline-block" />
                  </span>
                ) : (
                  '开始我的第一节课 🚀'
                )}
              </button>
            )}
          </div>
        )}
        {/* Desktop input bar (inside scroll flow) */}
        {!showPreferenceCards && (
          <div className="hidden md:flex gap-2">
            <input
              className="flex-1 bg-surface-container-lowest border border-outline-variant/20 rounded-full px-5 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
              placeholder="输入你的回复..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !isStreaming && handleSend()}
              disabled={isStreaming}
            />
            <button
              onClick={handleSend}
              disabled={isStreaming || !input.trim()}
              className="signature-gradient text-white w-11 h-11 rounded-full flex items-center justify-center shadow-lg disabled:opacity-50 flex-shrink-0"
            >
              <span className="material-symbols-outlined text-[20px]">send</span>
            </button>
          </div>
        )}
      </main>
      <MobileNav />
      {/* Mobile sticky input bar — above MobileNav */}
      {!showPreferenceCards && (
        <div className="fixed bottom-[var(--mobile-nav-height)] left-0 right-0 bg-background/95 backdrop-blur-md border-t border-outline-variant/15 px-4 py-3 z-40 md:hidden">
          <div className="max-w-2xl mx-auto flex gap-2">
            <input
              className="flex-1 bg-surface-container-lowest border border-outline-variant/20 rounded-full px-5 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
              placeholder="输入你的回复..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !isStreaming && handleSend()}
              disabled={isStreaming}
            />
            <button
              onClick={handleSend}
              disabled={isStreaming || !input.trim()}
              className="signature-gradient text-white w-11 h-11 rounded-full flex items-center justify-center shadow-lg disabled:opacity-50 flex-shrink-0"
            >
              <span className="material-symbols-outlined text-[20px]">send</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
