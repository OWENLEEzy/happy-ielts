'use client'
import { useState } from 'react'
import Image from 'next/image'
import { getRandomTogetherDogUrl, getRandomTeacherDogUrl } from '@/lib/constants'
import type { WritingFeedback } from '@/types'

interface Props {
  feedback: WritingFeedback
  onRetry?: () => void
}

export function FeedbackView({ feedback, onRetry }: Props) {
  const [scoreCardUrl] = useState(getRandomTogetherDogUrl)
  const [professorUrl] = useState(getRandomTeacherDogUrl)
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-5 pb-[calc(var(--mobile-nav-height)+24px)] md:pb-8">
      {/* Score card */}
      <div className="signature-gradient rounded-lg p-7 text-white shadow-xl relative overflow-hidden">
        <div className="absolute -top-8 -right-8 opacity-10 pointer-events-none">
          <span
            className="material-symbols-outlined text-[160px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            grade
          </span>
        </div>
        <div className="flex items-start justify-between relative z-10 mb-6">
          <div>
            <div className="text-[11px] font-black uppercase tracking-widest opacity-75 mb-1 font-label">
              综合评分
            </div>
            <div className="text-6xl font-black font-headline">{feedback.overall_score}</div>
            <div className="text-sm opacity-70 mt-1 font-label">/ 10</div>
          </div>
          <div className="relative w-16 h-16 rounded-full overflow-hidden border-2 border-white/30 flex-shrink-0">
            {scoreCardUrl && (
              <Image src={scoreCardUrl} fill sizes="64px" className="object-cover" alt="完成" />
            )}
          </div>
        </div>
        {feedback.rewrite_suggestions.length > 0 && (
          <div className="bg-white/15 backdrop-blur-sm rounded-lg p-4 text-sm leading-relaxed relative z-10">
            <div className="text-[10px] font-black uppercase tracking-wider opacity-75 mb-1 font-label">
              地道重写版本
            </div>
            {feedback.rewrite_suggestions[0]}
          </div>
        )}
      </div>

      {/* Grammar errors */}
      {feedback.grammar_errors.length > 0 && (
        <div className="bg-surface-container-lowest rounded-lg p-5 shadow-[0_4px_16px_color-mix(in_srgb,var(--primary)_7%,transparent)]">
          <div className="flex items-center gap-2 mb-4">
            <span
              className="material-symbols-outlined text-[19px] text-error"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              flag
            </span>
            <span className="font-bold font-headline text-on-surface">语法问题</span>
            <span className="ml-auto text-xs bg-error/10 text-error px-2 py-0.5 rounded-full font-label font-bold">
              {feedback.grammar_errors.length} 处
            </span>
          </div>
          {feedback.grammar_errors.map((e) => (
            <div
              key={`${e.original}-${e.correction}`}
              className="bg-surface-container-low rounded-lg p-4 mb-3 last:mb-0"
            >
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="line-through text-error text-sm font-bold font-label">
                  &ldquo;{e.original}&rdquo;
                </span>
                <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
                  arrow_forward
                </span>
                <span className="text-primary text-sm font-bold font-label">
                  &ldquo;{e.correction}&rdquo;
                </span>
              </div>
              <p className="text-xs text-on-surface-variant break-words">{e.explanation_zh}</p>
            </div>
          ))}
        </div>
      )}

      {/* Chinglish flags */}
      {feedback.chinglish_flags.length > 0 && (
        <div className="bg-error/5 border border-error/10 rounded-lg p-5">
          <div className="flex items-center gap-2 mb-4">
            <span
              className="material-symbols-outlined text-[19px] text-error"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              translate
            </span>
            <span className="font-bold font-headline text-on-surface">中式英语提醒</span>
            <span className="ml-auto text-xs bg-error/10 text-error px-2 py-0.5 rounded-full font-label font-bold">
              {feedback.chinglish_flags.length} 处
            </span>
          </div>
          {feedback.chinglish_flags.map((f) => (
            <div
              key={`${f.original}-${f.native_alternative}`}
              className="bg-surface-container-lowest rounded-lg p-4 mb-3 last:mb-0"
            >
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="line-through text-error text-sm font-bold font-label">
                  &ldquo;{f.original}&rdquo;
                </span>
                <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
                  arrow_forward
                </span>
                <span className="text-primary text-sm font-bold font-label">
                  &ldquo;{f.native_alternative}&rdquo;
                </span>
              </div>
              <p className="text-xs text-on-surface-variant break-words">{f.explanation_zh}</p>
              <p className="text-[10px] text-on-surface-variant/60 mt-1">已加入生词库，稍后复习</p>
            </div>
          ))}
        </div>
      )}

      {/* AI suggestion */}
      {feedback.rewrite_suggestions.length > 1 && (
        <div className="bg-tertiary-container/25 rounded-lg p-5 flex gap-3">
          <div className="relative w-10 h-10 rounded-full overflow-hidden flex-shrink-0 border-2 border-primary/20">
            {professorUrl && (
              <Image src={professorUrl} fill sizes="40px" className="object-cover" alt="tutor" />
            )}
          </div>
          <div>
            <div className="text-[11px] font-black text-primary uppercase tracking-wider font-label mb-1">
              Professor 金毛建议
            </div>
            <p className="text-sm text-on-surface leading-relaxed">
              {feedback.rewrite_suggestions[1]}
            </p>
          </div>
        </div>
      )}

      {/* Retry */}
      {onRetry && (
        <button
          onClick={onRetry}
          className="w-full bg-surface-container-highest text-on-surface py-3 rounded-full font-bold text-sm font-label hover:bg-surface-variant transition-colors flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-[17px]">refresh</span>
          重新写作
        </button>
      )}
    </div>
  )
}
