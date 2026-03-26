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
    await sendAction({ type: 'submit_writing', text }, (chunk) => {
      if (chunk.type === 'feedback') {
        onFeedback(chunk.result)
      }
    })
    setStreaming(false)
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-4rem)]">
      {/* ── Prompt section (fixed height) ─────────────────── */}
      <div className="flex-shrink-0 px-4 sm:px-6 pt-6 pb-5">
        <div className="max-w-3xl mx-auto">
          <div className="bg-surface-container-lowest rounded-xl p-5 shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)]">
            <div className="flex items-center gap-2 mb-3">
              <span className="signature-gradient text-white text-xs font-black px-3 py-1 rounded-full font-label capitalize">
                {task.mode.replace(/_/g, ' ')}
              </span>
              <span className="text-xs text-on-surface-variant font-label">{MIN} 词最低</span>
            </div>
            <p className="text-on-surface leading-relaxed font-medium text-sm sm:text-base max-h-[120px] overflow-y-auto">
              &ldquo;{task.instruction}&rdquo;
            </p>
          </div>
        </div>
      </div>

      {/* ── Divider ────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-outline-variant/20 mx-4 sm:mx-6" />

      {/* ── Editor section (stretches to fill) ─────────────── */}
      <div className="flex-1 min-h-0 flex flex-col px-4 sm:px-6 pt-4">
        <div className="max-w-3xl mx-auto flex flex-col flex-1 min-h-0 w-full">
          <textarea
            className="flex-1 min-h-0 w-full rounded-xl border border-outline-variant/20 bg-surface-container-low/60 p-5 resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40 text-on-surface leading-8 font-body text-sm"
            placeholder={`在此输入你的文章... (至少 ${MIN} 词)`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={streaming}
          />

          {/* ── Bottom bar ─────────────────────────────────── */}
          <div className="flex-shrink-0 flex items-center justify-between py-3 pb-[calc(var(--mobile-nav-height)+8px)] md:pb-4">
            <div className="flex items-center gap-3">
              <span className="text-sm font-bold font-label">
                <span className={wordCount >= MIN ? 'text-primary' : 'text-on-surface-variant'}>
                  {wordCount}
                </span>
                <span className="text-on-surface-variant"> / {MIN} 词</span>
              </span>
              <div className="w-20 h-1.5 bg-primary-container/20 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    wordCount >= MIN ? 'bg-primary' : 'bg-primary/40'
                  }`}
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
    </div>
  )
}
