'use client'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { sendAction } from '@/lib/sse'
import { useState } from 'react'

interface Props {
  word: string
  context: string
}

export function WordChip({ word, context }: Props) {
  const [explanation, setExplanation] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleClick = async () => {
    setIsOpen(true)
    if (explanation) return
    setIsLoading(true)
    let buffer = ''
    await sendAction({ type: 'explain_word', word, context }, (chunk) => {
      if (chunk.type === 'word_explanation') {
        buffer += chunk.result
        setExplanation(buffer)
      }
    })
    setIsLoading(false)
  }

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger
        className="cursor-pointer underline decoration-dotted underline-offset-2 hover:bg-yellow-100 rounded px-0.5 bg-transparent border-none p-0 font-inherit text-inherit"
        onClick={handleClick}
      >
        {word}
      </PopoverTrigger>
      <PopoverContent className="max-w-xs text-sm">
        {isLoading ? '解释中...' : explanation || '点击获取解释'}
      </PopoverContent>
    </Popover>
  )
}
