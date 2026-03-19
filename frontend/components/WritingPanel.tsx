'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WritingTask, WritingFeedback } from '@/types'

interface Props {
  task: WritingTask
  onFeedback: (feedback: WritingFeedback) => void
}

export function WritingPanel({ task, onFeedback }: Props) {
  const [text, setText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const wordCount = text.trim().split(/\s+/).filter(Boolean).length
  const meetsMinimum = wordCount >= task.min_words

  const handleSubmit = async () => {
    if (!meetsMinimum || isSubmitting) return
    setIsSubmitting(true)
    await sendAction(
      { type: 'submit_writing', text },
      chunk => {
        if (chunk.type === 'feedback') {
          onFeedback(chunk.result)
        }
      },
    )
    setIsSubmitting(false)
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">写作任务</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="leading-relaxed">{task.instruction}</p>
          <p className="text-sm text-gray-500 mt-2">最少 {task.min_words} 字</p>
        </CardContent>
      </Card>

      <Textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="用英文写作..."
        className="min-h-48 text-base"
      />

      <div className="flex justify-between items-center">
        <span className={`text-sm ${meetsMinimum ? 'text-green-600' : 'text-gray-400'}`}>
          {wordCount} / {task.min_words} words
        </span>
        <Button onClick={handleSubmit} disabled={!meetsMinimum || isSubmitting}>
          {isSubmitting ? '批改中...' : '提交写作'}
        </Button>
      </div>
    </div>
  )
}
