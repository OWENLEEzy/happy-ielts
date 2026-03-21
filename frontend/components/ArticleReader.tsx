'use client'
import { useState, useEffect } from 'react'
import { FullArticle } from './FullArticle'
import { sendAction } from '@/lib/sse'
import { getRandomTeacherDogUrl } from '@/lib/constants'
import type { Article } from '@/types'

interface Props {
  article: Article
  onDone: () => void
}

export function ArticleReader({ article, onDone }: Props) {
  const [showTip, setShowTip] = useState(true)
  const [doneLoading, setDoneLoading] = useState(false)
  const [dogUrl, setDogUrl] = useState<string | null>(null)

  useEffect(() => {
    setDogUrl(getRandomTeacherDogUrl())
  }, [])

  const handleDone = async () => {
    setDoneLoading(true)
    await sendAction({ type: 'done_reading' }, () => {})
    onDone()
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6 pb-[calc(var(--mobile-nav-height)+24px)] md:pb-8">
      {/* Article meta */}
      <div>
        <div className="flex flex-wrap gap-2 mb-4">
          {article.topic_tags.map((tag) => (
            <span
              key={tag}
              className="bg-primary/10 text-primary px-3 py-1 rounded-full text-xs font-bold font-label"
            >
              {tag}
            </span>
          ))}
          <span className="bg-tertiary/10 text-tertiary px-3 py-1 rounded-full text-xs font-bold font-label capitalize">
            {article.article_logic.replace(/_/g, ' ')}
          </span>
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold font-headline text-on-surface mb-2">
          {article.original_title}
        </h1>
        <div className="flex items-center gap-2 text-xs text-on-surface-variant font-label">
          <span
            className="material-symbols-outlined text-[14px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            smart_toy
          </span>
          AI 已高亮 {article.highlight_indices.length} 个核心段落 · 紫色高亮段落是今日写作的核心论点
        </div>
      </div>

      {/* AI tutor tip */}
      {showTip && (
        <div className="bg-tertiary-container/25 border border-primary/10 rounded-lg p-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-full overflow-hidden border border-primary/20 flex-shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {dogUrl && <img src={dogUrl} className="w-full h-full object-cover" alt="tutor" />}
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-black text-primary uppercase tracking-wider font-label mb-1">
              Professor 金毛提示
            </div>
            <p className="text-sm text-on-surface leading-relaxed">
              注意<span className="font-bold text-primary">紫色高亮段落</span>——
              这些是今日写作任务的核心论点来源。
            </p>
          </div>
          <button
            onClick={() => setShowTip(false)}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>
      )}

      {/* Article body */}
      <FullArticle article={article} />

      {/* CTA */}
      <div className="bg-primary-container/20 rounded-lg p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-8">
        <div>
          <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label mb-1">
            阅读完成
          </div>
          <h3 className="text-lg font-bold font-headline text-on-surface">准备好开始写作了吗？</h3>
          <p className="text-sm text-on-surface-variant mt-1">基于本文的写作任务已就绪</p>
        </div>
        <button
          onClick={handleDone}
          disabled={doneLoading}
          className="signature-gradient text-white px-6 py-2.5 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-60 flex items-center gap-2 whitespace-nowrap"
        >
          {doneLoading ? (
            <>
              <span className="dot1 w-2 h-2 bg-white rounded-full inline-block" />
              <span className="dot2 w-2 h-2 bg-white rounded-full inline-block" />
              <span className="dot3 w-2 h-2 bg-white rounded-full inline-block" />
            </>
          ) : (
            <>
              <span className="material-symbols-outlined text-[18px]">edit_note</span>
              开始写作
            </>
          )}
        </button>
      </div>
    </div>
  )
}
