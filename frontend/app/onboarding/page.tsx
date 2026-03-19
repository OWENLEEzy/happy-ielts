'use client'
import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { sendOnboardingMessage } from '@/lib/sse'
import { useOnboardingStatus } from '@/hooks/useLesson'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { DOG_GOLDEN } from '@/lib/constants'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function OnboardingPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: '你好！我是你的语言学习顾问。先告诉我，你学英语最迫切想解决什么问题？' }
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [showPreferenceCards, setShowPreferenceCards] = useState(false)
  const [bandwidth, setBandwidth] = useState<number | null>(null)
  const [writingMode, setWritingMode] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { data: status, mutate } = useOnboardingStatus()

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
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setIsStreaming(true)

    let assistantContent = ''
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      await sendOnboardingMessage(userMsg, (token) => {
        assistantContent += token
        setMessages(prev => {
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
    await fetch('/api/onboarding/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bandwidth_minutes: bandwidth, writing_mode: writingMode }),
    })
    await fetch('/api/planner/run', { method: 'POST' })
    router.push('/lesson')
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-8 pb-24 md:pb-8 flex flex-col gap-4">
        {/* Tutor intro card */}
        <div className="flex items-center gap-3 bg-tertiary-container/25 rounded-lg p-4 border border-primary/10">
          <div className="w-12 h-12 rounded-full overflow-hidden border-2 border-primary/20 flex-shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={DOG_GOLDEN} className="w-full h-full object-cover" alt="顾问" />
          </div>
          <div>
            <div className="text-[11px] font-black text-primary uppercase tracking-wider font-label">
              Professor 金毛
            </div>
            <div className="text-xs text-on-surface-variant">你的专属语言学习顾问</div>
          </div>
        </div>

        {/* Message list */}
        <div className="flex-1 space-y-3 overflow-y-auto">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full overflow-hidden border border-primary/20 mr-2 flex-shrink-0 mt-1">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={DOG_GOLDEN} className="w-full h-full object-cover" alt="" />
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
              <div className="w-7 h-7 rounded-full overflow-hidden border border-primary/20 mr-2 flex-shrink-0 mt-1">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={DOG_GOLDEN} className="w-full h-full object-cover" alt="" />
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
                {[15, 25, 40].map(mins => (
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
                  { val: 'ielts',        label: '雅思备考' },
                  { val: 'both',         label: '两者都要' },
                ].map(o => (
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
                className="w-full signature-gradient text-white py-3 rounded-full font-bold font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
              >
                开始我的第一节课 🚀
              </button>
            )}
          </div>
        )}

        {/* Input bar */}
        {!showPreferenceCards && (
          <div className="flex gap-2">
            <input
              className="flex-1 bg-surface-container-lowest border border-outline-variant/20 rounded-full px-5 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
              placeholder="输入你的回复..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !isStreaming && handleSend()}
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
    </div>
  )
}
