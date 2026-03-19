'use client'
import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { sendOnboardingMessage } from '@/lib/sse'
import { useOnboardingStatus } from '@/hooks/useLesson'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'

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
    <div className="max-w-2xl mx-auto p-4 h-screen flex flex-col">
      <h1 className="text-xl font-bold mb-4">入学评估</h1>

      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-xl px-4 py-2 ${
              m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}>
              {m.content || (isStreaming && m.role === 'assistant' ? '...' : '')}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {showPreferenceCards ? (
        <Card className="mb-4">
          <CardContent className="pt-4 space-y-4">
            <p className="font-medium">最后两步：</p>
            <div>
              <p className="text-sm mb-2">每日学习时长</p>
              <div className="flex gap-2">
                {[15, 25].map(m => (
                  <Button
                    key={m}
                    variant={bandwidth === m ? 'default' : 'outline'}
                    onClick={() => setBandwidth(m)}
                  >{m} 分钟</Button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-sm mb-2">写作目标</p>
              <div className="flex gap-2 flex-wrap">
                {[['professional', '职场流'], ['ielts', '雅思流'], ['both', '两者']].map(([val, label]) => (
                  <Button
                    key={val}
                    variant={writingMode === val ? 'default' : 'outline'}
                    onClick={() => setWritingMode(val)}
                  >{label}</Button>
                ))}
              </div>
            </div>
            <Button
              className="w-full"
              disabled={!bandwidth || !writingMode}
              onClick={handlePreferenceSubmit}
            >
              开始准备今日内容 →
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="输入你的回答..."
            disabled={isStreaming}
          />
          <Button onClick={handleSend} disabled={isStreaming || !input.trim()}>
            发送
          </Button>
        </div>
      )}
    </div>
  )
}
