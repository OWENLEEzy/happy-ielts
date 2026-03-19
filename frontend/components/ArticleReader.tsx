'use client'
import { useState } from 'react'
import { FullArticle } from './FullArticle'
import { sendAction } from '@/lib/sse'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { Article } from '@/types'

interface Props {
  article: Article
  onDoneReading: () => void
}

export function ArticleReader({ article, onDoneReading }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [analysis, setAnalysis] = useState('')
  const [currentSentence, setCurrentSentence] = useState('')

  const handleSentenceClick = async (sentence: string) => {
    setCurrentSentence(sentence)
    setDrawerOpen(true)
    setAnalysis('')
    let buffer = ''
    await sendAction(
      { type: 'analyze_sentence', sentence },
      chunk => {
        if (chunk.type === 'sentence_analysis') {
          buffer += chunk.result
          setAnalysis(buffer)
        }
      },
    )
  }

  const handleDoneReading = async () => {
    await sendAction({ type: 'done_reading' }, () => {})
    onDoneReading()
  }

  return (
    <div className="max-w-3xl mx-auto p-4">
      <FullArticle article={article} onSentenceClick={handleSentenceClick} />

      <div className="mt-6 flex justify-end">
        <Button onClick={handleDoneReading} size="lg">
          完成阅读 → 去写作
        </Button>
      </div>

      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="bottom" className="h-64">
          <SheetHeader>
            <SheetTitle className="text-sm text-gray-500 font-normal">句子分析</SheetTitle>
          </SheetHeader>
          <p className="text-sm italic text-gray-600 mb-2">&ldquo;{currentSentence}&rdquo;</p>
          <p className="text-sm leading-relaxed">{analysis || '分析中...'}</p>
        </SheetContent>
      </Sheet>
    </div>
  )
}
