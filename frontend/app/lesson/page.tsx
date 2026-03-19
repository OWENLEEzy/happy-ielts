'use client'
import { useReducer, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { lessonReducer, initialState } from './reducer'
import { FillBlankCard } from '@/components/FillBlankCard'
import { ArticleReader } from '@/components/ArticleReader'
import { WritingPanel } from '@/components/WritingPanel'
import { FeedbackView } from '@/components/FeedbackView'
import { useTodayLesson, usePlannerStatus } from '@/hooks/useLesson'
import { startLesson } from '@/lib/sse'
import type { SSEChunk } from '@/types'

export default function LessonPage() {
  const searchParams = useSearchParams()
  const isLoading = searchParams.get('loading') === 'true'
  const { data: lesson, isLoading: lessonLoading } = useTodayLesson()
  const { data: plannerStatus } = usePlannerStatus()
  const [state, dispatch] = useReducer(lessonReducer, initialState)

  useEffect(() => {
    if (!lesson) return

    const handleChunk = (chunk: SSEChunk) => {
      switch (chunk.type) {
        case 'fill_blank':
          dispatch({ type: 'FILL_BLANK_RECEIVED', question: chunk.question, word: chunk.word })
          break
        case 'awaiting_action':
          dispatch({ type: 'AWAITING_READING' })
          break
        case 'writing_task':
          dispatch({ type: 'WRITING_TASK_RECEIVED' })
          break
        case 'feedback':
          dispatch({ type: 'FEEDBACK_DONE', feedback: chunk.result })
          break
      }
    }

    startLesson(handleChunk).catch(console.error)
  }, [lesson])

  if (isLoading || !plannerStatus?.ready) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center space-y-2">
          <p className="text-lg">今日内容准备中...</p>
          <p className="text-sm text-gray-500">DeepAgent 正在为你抓取文章</p>
        </div>
      </div>
    )
  }

  if (lessonLoading || !lesson) {
    return <div className="flex items-center justify-center h-screen">加载中...</div>
  }

  return (
    <main className="min-h-screen pb-16">
      {state.phase === 'review' && state.fillBlank && (
        <div className="flex items-center justify-center min-h-screen">
          <FillBlankCard
            question={state.fillBlank.question}
            word={state.fillBlank.word}
            onDone={() => dispatch({ type: 'REVIEW_DONE' })}
          />
        </div>
      )}

      {state.phase === 'reading' && (
        <ArticleReader
          article={lesson.article}
          onDoneReading={() => dispatch({ type: 'READING_DONE' })}
        />
      )}

      {state.phase === 'writing' && (
        <WritingPanel
          task={lesson.task}
          onFeedback={feedback => dispatch({ type: 'FEEDBACK_DONE', feedback })}
        />
      )}

      {state.phase === 'feedback' && state.feedback && (
        <FeedbackView feedback={state.feedback} />
      )}
    </main>
  )
}
