'use client'
import { useState } from 'react'
import { sendAction } from '@/lib/sse'

interface Props {
  word: string
  context: string
  onExplained?: (explanation: string) => void
}

export function WordChip({ word, context, onExplained }: Props) {
  const [loading, setLoading] = useState(false)

  const handleClick = async () => {
    if (loading) return
    setLoading(true)
    let buffer = ''
    await sendAction(
      { type: 'explain_word', word, context },
      chunk => {
        if (chunk.type === 'word_explanation') {
          buffer += chunk.result
          onExplained?.(buffer)
        }
      },
    )
    setLoading(false)
  }

  return (
    <span
      className={`vocab-word inline ${loading ? 'opacity-60' : 'hover:opacity-80'} transition-opacity`}
      onClick={handleClick}
      title="点击查看释义"
    >
      {word}
    </span>
  )
}
