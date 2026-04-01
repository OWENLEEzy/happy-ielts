'use client'
import { useState, useEffect, useRef } from 'react'
import { DogAvatar } from '@/components/DogAvatar'
import { sendAction } from '@/lib/sse'
import type { SSEChunk } from '@/types'

interface Props {
  question: string
  word: string
  onChunk: (chunk: SSEChunk) => void
}

export function FillBlankCard({ question, word, onChunk }: Props) {
  const [answer, setAnswer] = useState('')
  const startTimeRef = useRef<number>(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    startTimeRef.current = Date.now()
    inputRef.current?.focus()
  }, [])

  const [hint, setHint] = useState<string | null>(null)
  const [attempts, setAttempts] = useState(0)
  const [revealed, setRevealed] = useState(false)

  const handleSubmit = async () => {
    const response_seconds = (Date.now() - startTimeRef.current) / 1000
    const isCorrect = answer.trim().toLowerCase() === word.toLowerCase()

    if (isCorrect || attempts >= 2) {
      await sendAction(
        { type: 'fill_blank_answer', answer: isCorrect ? answer : word, response_seconds },
        onChunk,
      )
      return
    }

    const newAttempts = attempts + 1
    setAttempts(newAttempts)
    if (newAttempts === 1) {
      setHint(`提示：注意词形和搭配`)
    } else if (newAttempts === 2) {
      setHint(`首字母提示：${word[0].toUpperCase()}...`)
    }
  }

  const handleReveal = async () => {
    const response_seconds = (Date.now() - startTimeRef.current) / 1000
    setRevealed(true)
    await sendAction({ type: 'fill_blank_answer', answer: word, response_seconds }, onChunk)
  }

  return (
    <div className="flex flex-col h-full min-h-screen">
      {/* Scrollable content area */}
      <div className="flex-1 overflow-y-auto px-4 pt-8 pb-32">
        {/* Section label */}
        <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label text-center mb-6">
          每日复习关卡
        </div>

        {/* Card */}
        <div className="w-full max-w-md mx-auto bg-surface-container-lowest rounded-lg shadow-[0_8px_32px_color-mix(in_srgb,var(--primary)_12%,transparent)] p-8 space-y-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="flex-shrink-0">
              <DogAvatar
                role="teacher"
                size={32}
                emphasis="card"
                alt="Professor 金毛提示"
                seedKey="fill-blank-card"
              />
            </div>
            <p className="text-xs font-bold text-on-surface-variant font-label">
              填入正确的词汇，解锁今日课程
            </p>
          </div>

          <p className="text-lg text-on-surface leading-8 font-medium">{question}</p>

          {hint && (
            <div className="bg-primary/8 border border-primary/15 rounded-lg px-4 py-2 text-sm text-primary font-label">
              💡 {hint}
            </div>
          )}

          {revealed && (
            <div className="bg-primary text-white rounded-lg px-4 py-2 text-sm font-bold font-label text-center">
              答案：{word} ✓
            </div>
          )}

          {attempts >= 2 && !revealed && (
            <button
              onClick={handleReveal}
              className="w-full text-on-surface-variant text-xs font-label hover:text-primary transition-colors py-1"
            >
              放弃并查看答案
            </button>
          )}
        </div>

        {/* Attempt dots */}
        <div className="flex gap-2 justify-center mt-6">
          {[0, 1, 2].map((dot) => (
            <div
              key={`dot-${dot}`}
              className={`w-2 h-2 rounded-full ${dot < attempts ? 'bg-error' : 'bg-outline-variant'}`}
            />
          ))}
        </div>
      </div>

      {/* Sticky bottom input bar */}
      {!revealed && (
        <div className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur-md border-t border-outline-variant/15 px-4 py-3 md:pb-3 pb-safe">
          <div className="max-w-md mx-auto flex gap-2">
            <input
              ref={inputRef}
              className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-full px-5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="填写答案..."
            />
            <button
              onClick={handleSubmit}
              className="signature-gradient text-white px-5 py-2.5 rounded-full font-bold text-sm font-label shadow-md hover:scale-105 transition-transform flex-shrink-0"
            >
              确认
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
