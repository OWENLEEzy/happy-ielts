'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface Props {
  question: string
  word: string
  onDone: () => void
}

export function FillBlankCard({ question, word, onDone }: Props) {
  const [answer, setAnswer] = useState('')
  const [startTime] = useState(Date.now())
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
      setHint(`词性提示：动词（verb）`)
    } else if (newAttempts === 2) {
      setHint(`首字母提示：${word[0].toUpperCase()}...`)
    }
  }

  const handleReveal = async () => {
    const response_seconds = (Date.now() - startTime) / 1000
    await sendAction(
      { type: 'fill_blank_answer', answer: word, response_seconds: 30 },
      () => {},
    )
    setRevealed(true)
    setTimeout(onDone, 2000)
  }

  return (
    <Card className="max-w-lg mx-auto">
      <CardHeader>
        <CardTitle className="text-base">每日复习</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-lg leading-relaxed">{question}</p>
        {hint && <p className="text-sm text-blue-600">{hint}</p>}
        {revealed && <p className="text-green-600 font-medium">答案：{word}</p>}
        {!revealed && (
          <div className="flex gap-2">
            <Input
              value={answer}
              onChange={e => setAnswer(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              placeholder="填写答案..."
            />
            <Button onClick={handleSubmit}>确认</Button>
            {attempts >= 2 && (
              <Button variant="ghost" onClick={handleReveal}>揭晓</Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
