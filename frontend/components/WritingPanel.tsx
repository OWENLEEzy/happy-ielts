'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'
import type { WritingTask, WritingFeedback } from '@/types'

interface Props {
  task: WritingTask
  onFeedback: (feedback: WritingFeedback) => void
}

export function WritingPanel({ task, onFeedback }: Props) {
  const [text, setText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const wordCount = text.trim() === '' ? 0 : text.trim().split(/\s+/).length
  const MIN = task.min_words

  const handleSubmit = async () => {
    if (wordCount < MIN || streaming) return
    setStreaming(true)
    await sendAction(
      { type: 'submit_writing', text },
      chunk => {
        if (chunk.type === 'feedback') {
          onFeedback(chunk.result)
        }
      },
    )
    setStreaming(false)
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-5 pb-24">
      {/* Task prompt */}
      <div className="bg-surface-container-lowest rounded-lg p-6 shadow-[0_4px_16px_rgba(109,74,179,0.07)]">
        <div className="flex items-center gap-2 mb-3">
          <span className="signature-gradient text-white text-xs font-black px-3 py-1 rounded-full font-label capitalize">
            {task.mode.replace('_', ' ')}
          </span>
          <span className="text-xs text-on-surface-variant font-label">{MIN} 词最低</span>
        </div>
        <p className="text-on-surface leading-relaxed font-medium">&ldquo;{task.instruction}&rdquo;</p>
      </div>

      {/* Editor */}
      <div className="bg-surface-container-lowest rounded-lg p-6 shadow-[0_4px_16px_rgba(109,74,179,0.07)]">
        <textarea
          className="w-full rounded-lg border border-outline-variant/20 bg-surface-container-low p-5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40 text-on-surface leading-8 font-body text-sm min-h-[240px]"
          placeholder={`在此输入你的文章... (至少 ${MIN} 词)`}
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={streaming}
        />
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold font-label">
              <span className={wordCount >= MIN ? 'text-primary' : 'text-on-surface-variant'}>
                {wordCount}
              </span>
              <span className="text-on-surface-variant"> / {MIN} 词</span>
            </span>
            <div className="w-20 h-2 bg-primary-container/20 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${wordCount >= MIN ? 'bg-primary' : 'bg-primary/40'}`}
                style={{ width: `${Math.min(100, (wordCount / MIN) * 100)}%` }}
              />
            </div>
          </div>
          <button
            onClick={handleSubmit}
            disabled={wordCount < MIN || streaming}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-full font-bold text-sm font-label transition-all ${
              wordCount >= MIN && !streaming
                ? 'signature-gradient text-white shadow-lg shadow-primary/25 hover:scale-105 cursor-pointer'
                : 'bg-surface-container-highest text-on-surface-variant cursor-not-allowed opacity-60'
            }`}
          >
            {streaming ? (
              <>
                <span className="dot1 w-2 h-2 bg-white rounded-full inline-block" />
                <span className="dot2 w-2 h-2 bg-white rounded-full inline-block" />
                <span className="dot3 w-2 h-2 bg-white rounded-full inline-block" />
                <span>AI 批改中</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[17px]">send</span>
                提交批改
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
