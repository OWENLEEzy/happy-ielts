'use client'
import { useState } from 'react'
import { WordChip } from './WordChip'
import styles from './FullArticle.module.scss'
import type { Article } from '@/types'

interface Props {
  article: Article
  onWordExplained?: (word: string, explanation: string) => void
}

function renderTokens(text: string, onExplained: (word: string, explanation: string) => void) {
  return text.split(/(\s+)/).map((token, i) => {
    if (/\s+/.test(token)) return <span key={i}>{token}</span>
    const word = token.replace(/[.,!?;:'"()\[\]]/g, '')
    if (!word) return <span key={i}>{token}</span>
    return (
      <WordChip
        key={i}
        word={word}
        context={text}
        onExplained={(explanation) => onExplained(word, explanation)}
      />
    )
  })
}

export function FullArticle({ article, onWordExplained }: Props) {
  const [activeExplanation, setActiveExplanation] = useState<{ word: string; text: string } | null>(
    null,
  )
  const paragraphs = article.full_text.split('\n\n').filter(Boolean)

  const handleExplained = (word: string, explanation: string) => {
    setActiveExplanation({ word, text: explanation })
    onWordExplained?.(word, explanation)
  }

  return (
    <div className="space-y-5 text-base leading-8 text-on-surface">
      {/* Active explanation popover */}
      {activeExplanation && (
        <div className="sticky top-20 z-10 bg-on-surface text-surface rounded-lg px-4 py-3 text-sm shadow-xl flex items-start justify-between gap-3">
          <div>
            <span className="font-bold text-primary-fixed">{activeExplanation.word}</span>
            <span className="ml-2 opacity-90">{activeExplanation.text}</span>
          </div>
          <button
            onClick={() => setActiveExplanation(null)}
            className="text-surface/60 hover:text-surface flex-shrink-0 mt-0.5"
          >
            ✕
          </button>
        </div>
      )}

      {paragraphs.map((para, idx) => {
        const isHighlighted = article.highlight_indices.includes(idx)
        return (
          <p key={idx} className={`relative ${isHighlighted ? styles.highlighted : ''}`}>
            {renderTokens(para, handleExplained)}
          </p>
        )
      })}
    </div>
  )
}
