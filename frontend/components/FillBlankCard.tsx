'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'
import { DOG_GOLDEN } from '@/lib/constants'

interface Props {
  question: string
  word: string
  onDone: () => void
}

export function FillBlankCard({ question, word, onDone }: Props) {
  const [answer, setAnswer] = useState('')
  const [startTime] = useState(() => Date.now())
  const [hint, setHint] = useState<string | null>(null)
  const [attempts, setAttempts] = useState(0)
  const [revealed, setRevealed] = useState(false)

  const handleSubmit = async () => {
    const response_seconds = (Date.now() - startTime) / 1000
    const isCorrect = answer.trim().toLowerCase() === word.toLowerCase()

    if (isCorrect || attempts >= 2) {
      await sendAction(
        { type: 'fill_blank_answer', answer: isCorrect ? answer : word, response_seconds },
        () => {},
      )
      onDone()
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
    const response_seconds = (Date.now() - startTime) / 1000
    await sendAction({ type: 'fill_blank_answer', answer: word, response_seconds }, () => {})
    setRevealed(true)
    setTimeout(onDone, 2000)
  }

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 py-8 space-y-6">
      {/* Section label */}
      <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
        每日复习关卡
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-surface-container-lowest rounded-lg shadow-[0_8px_32px_rgba(109,74,179,0.12)] p-8 space-y-5">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-full overflow-hidden border border-primary/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={DOG_GOLDEN} className="w-full h-full object-cover" alt="tutor" />
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

        {!revealed && (
          <div className="flex gap-2">
            <input
              className="flex-1 bg-surface-container-low border border-outline-variant/20 rounded-full px-5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="填写答案..."
            />
            <button
              onClick={handleSubmit}
              className="signature-gradient text-white px-5 py-2.5 rounded-full font-bold text-sm font-label shadow-md hover:scale-105 transition-transform"
            >
              确认
            </button>
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
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full ${i < attempts ? 'bg-error' : 'bg-outline-variant'}`}
          />
        ))}
      </div>
    </div>
  )
}
