'use client'
import { useReducer, useEffect, useState, useCallback, Suspense } from 'react'
import Image from 'next/image'
import { useSearchParams } from 'next/navigation'
import { lessonReducer, initialState } from './reducer'
import { FillBlankCard } from '@/components/FillBlankCard'
import { ArticleReader } from '@/components/ArticleReader'
import { WritingPanel } from '@/components/WritingPanel'
import { FeedbackView } from '@/components/FeedbackView'
import { Header } from '@/components/Header'
import { LessonSidebar } from '@/components/LessonSidebar'
import { MobileNav } from '@/components/MobileNav'
import { useTodayLesson, usePlannerStatus } from '@/hooks/useLesson'
import { client } from '@/lib/client'
import { startLesson } from '@/lib/sse'
import { getRandomTeacherDogUrl } from '@/lib/constants'
import type { SSEChunk } from '@/types'

const LoadingDots = () => (
  <div className="flex gap-1.5 justify-center">
    <span className="dot1 w-3 h-3 bg-primary rounded-full inline-block" />
    <span className="dot2 w-3 h-3 bg-primary rounded-full inline-block" />
    <span className="dot3 w-3 h-3 bg-primary rounded-full inline-block" />
  </div>
)

function LessonContent() {
  const searchParams = useSearchParams()
  const isLoading = searchParams.get('loading') === 'true'
  const { data: lesson, isLoading: lessonLoading } = useTodayLesson()
  const { data: plannerStatus } = usePlannerStatus()
  const [state, dispatch] = useReducer(lessonReducer, initialState)
  const [loadingDogUrl] = useState(getRandomTeacherDogUrl)

  const handleChunk = useCallback((chunk: SSEChunk) => {
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
    }
  }, [])

  useEffect(() => {
    if (!lesson) return

    const controller = new AbortController()

    startLesson(handleChunk, controller.signal).catch((err) => {
      if (err.name !== 'AbortError') console.error(err)
    })

    return () => controller.abort()
  }, [lesson, handleChunk])

  if (isLoading || !plannerStatus?.ready) {
    const isError = plannerStatus?.status === 'error'
    const isRunning = plannerStatus?.status === 'running'

    return (
      <main className="max-w-3xl mx-auto px-6 py-12 pb-[calc(var(--mobile-nav-height)+16px)] md:pb-12 text-center space-y-6 flex-1">
        <div
          className={`rounded-lg p-10 relative overflow-hidden ${isError ? 'bg-error-container/20' : 'bg-primary-container/20'}`}
        >
          <div className="relative z-10">
            <div className="relative w-24 h-24 rounded-full overflow-hidden border-4 border-white shadow-xl mx-auto mb-6">
              {loadingDogUrl && (
                <Image
                  src={loadingDogUrl}
                  fill
                  sizes="96px"
                  className="object-cover"
                  alt="准备中"
                />
              )}
            </div>

            {isError ? (
              <>
                <h1 className="text-2xl font-extrabold font-headline text-error mb-3">
                  课程生成失败
                </h1>
                <p className="text-on-surface-variant mb-2 text-sm">
                  Planner 遇到了问题，请检查 API Key 或网络连接后重试。
                </p>
                {plannerStatus.error && (
                  <p className="text-xs text-error/70 font-mono bg-error-container/30 rounded px-3 py-2 mb-6 text-left break-all">
                    {plannerStatus.error}
                  </p>
                )}
                <button
                  onClick={() => client.POST('/api/planner/jobs', {}).catch(console.error)}
                  className="signature-gradient text-white px-6 py-2 rounded-full font-bold text-sm font-label shadow-lg hover:scale-105 transition-transform"
                >
                  重新生成课程
                </button>
              </>
            ) : (
              <>
                <h1 className="text-2xl font-extrabold font-headline text-primary mb-3">
                  今日课程准备中…
                </h1>
                <p className="text-on-surface-variant mb-8">
                  DeepAgent Planner 正在为你抓取今日文章和生成写作任务，请稍候。
                </p>
                {isRunning && (
                  <div className="mb-8">
                    <LoadingDots />
                  </div>
                )}
                {!isRunning && (
                  <button
                    onClick={() => client.POST('/api/planner/jobs', {}).catch(console.error)}
                    className="bg-surface-container-highest text-on-surface px-6 py-2 rounded-full font-bold text-sm font-label hover:bg-surface-variant transition-colors"
                  >
                    手动触发课程生成
                  </button>
                )}
              </>
            )}
          </div>
          <div className="absolute -right-10 -bottom-10 opacity-5 pointer-events-none">
            <span className="material-symbols-outlined text-[200px] text-primary">
              {isError ? 'error' : 'menu_book'}
            </span>
          </div>
        </div>
      </main>
    )
  }

  if (lessonLoading || !lesson) {
    return (
      <main className="flex items-center justify-center flex-1 py-20 pb-[calc(var(--mobile-nav-height)+20px)] md:pb-20">
        <LoadingDots />
      </main>
    )
  }

  return (
    <div className="flex flex-1">
      <LessonSidebar phase={state.phase} articleTitle={lesson.article.original_title} />
      <main className="flex-1 overflow-y-auto">
        {state.phase === 'review' && state.fillBlank && (
          <FillBlankCard
            question={state.fillBlank.question}
            word={state.fillBlank.word}
            onChunk={handleChunk}
          />
        )}

        {state.phase === 'reading' && (
          <ArticleReader
            article={lesson.article}
            onDone={() => dispatch({ type: 'READING_DONE' })}
          />
        )}

        {state.phase === 'writing' && (
          <WritingPanel
            task={lesson.task}
            onFeedback={(feedback) => dispatch({ type: 'FEEDBACK_DONE', feedback })}
          />
        )}

        {state.phase === 'feedback' && state.feedback && (
          <FeedbackView
            feedback={state.feedback}
            onRetry={() => dispatch({ type: 'WRITING_TASK_RECEIVED' })}
          />
        )}
      </main>
    </div>
  )
}

export default function LessonPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <Suspense
        fallback={
          <main className="flex items-center justify-center flex-1 py-20">
            <LoadingDots />
          </main>
        }
      >
        <LessonContent />
      </Suspense>
      <MobileNav />
    </div>
  )
}
