'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useGeneralLesson } from '@/hooks/useGeneralLesson'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'

export default function LessonPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.projectId)
  const lessonId = Number(params.lessonId)
  const { phase, studyGuide, lessonTitle, quiz, qaHistory, start, sendAction, abort } =
    useGeneralLesson(projectId, lessonId)

  const [quizAnswers, setQuizAnswers] = useState<string[]>([])
  const [qaInput, setQaInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    start()
    return () => abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (quiz.length) setQuizAnswers(Array(quiz.length).fill(''))
  }, [quiz])

  const handleNext = async () => {
    setIsLoading(true)
    await sendAction({ type: 'next' })
    setIsLoading(false)
  }

  const handleSubmitQuiz = async () => {
    setIsLoading(true)
    await sendAction({ type: 'submit', answers: quizAnswers })
    setIsLoading(false)
  }

  const handleAsk = async () => {
    if (!qaInput.trim()) return
    const q = qaInput.trim()
    setQaInput('')
    setIsLoading(true)
    await sendAction({ type: 'question', question: q })
    setIsLoading(false)
  }

  const handleExit = async () => {
    await sendAction({ type: 'exit' })
    router.push(`/learn/${projectId}`)
  }

  const s = {
    bg: '#0f0d1a',
    fg: '#e8e0d0',
    card: '#1a1730',
    border: '#2e2850',
    amber: '#c9a84c',
  }

  if (phase === 'done') {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: s.bg, color: s.fg }}>
        <Header dark />
        <main
          className="flex-1 flex flex-col items-center justify-center px-4"
          style={{ background: s.bg, color: s.fg }}
        >
          <div className="text-5xl mb-4">🎉</div>
          <h2 className="text-2xl font-semibold mb-2" style={{ color: s.amber }}>
            课程完成
          </h2>
          <p className="opacity-60 mb-8 text-sm">你已完成本节课的学习</p>
          <button
            className="px-6 py-3 rounded-xl font-medium"
            style={{ background: s.amber, color: s.bg }}
            onClick={() => router.push(`/learn/${projectId}`)}
          >
            返回课程
          </button>
        </main>
        <MobileNav />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: s.bg, color: s.fg }}>
      <Header dark />
      <main className="flex-1 flex flex-col" style={{ background: s.bg, color: s.fg }}>
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: s.border }}
        >
          <span className="text-base font-semibold" style={{ color: s.amber }}>
            {lessonTitle || '正在加载...'}
          </span>
          <span
            className="text-sm px-3 py-1 rounded-full capitalize"
            style={{ background: s.card, border: `1px solid ${s.border}` }}
          >
            {phase === 'reading'
              ? '阅读'
              : phase === 'quiz'
                ? '测验'
                : phase === 'free_qa'
                  ? '问答'
                  : phase}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl w-full mx-auto">
          {/* Reading phase */}
          {phase === 'reading' && (
            <div>
              <div
                className="rounded-xl p-6 text-sm leading-relaxed whitespace-pre-wrap mb-6"
                style={{ background: s.card, border: `1px solid ${s.border}` }}
              >
                {studyGuide || (
                  <span className="opacity-40 animate-pulse">正在加载学习材料...</span>
                )}
              </div>
              <button
                className="w-full py-3 rounded-xl font-medium disabled:opacity-40"
                style={{ background: s.amber, color: s.bg }}
                onClick={handleNext}
                disabled={isLoading || !studyGuide}
              >
                {isLoading ? '请稍候...' : '继续 →'}
              </button>
            </div>
          )}

          {/* Quiz phase */}
          {phase === 'quiz' && (
            <div>
              <h3 className="text-lg font-semibold mb-4" style={{ color: s.amber }}>
                随堂测验
              </h3>
              <div className="flex flex-col gap-4 mb-6">
                {quiz.map((q, i) => (
                  <div
                    key={i}
                    className="rounded-xl p-4"
                    style={{ background: s.card, border: `1px solid ${s.border}` }}
                  >
                    <p className="text-sm mb-3 font-medium">
                      {i + 1}. {q.q}
                    </p>
                    <input
                      className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.fg }}
                      placeholder="你的回答..."
                      value={quizAnswers[i] ?? ''}
                      onChange={(e) =>
                        setQuizAnswers((prev) => {
                          const next = [...prev]
                          next[i] = e.target.value
                          return next
                        })
                      }
                    />
                  </div>
                ))}
              </div>
              <button
                className="w-full py-3 rounded-xl font-medium disabled:opacity-40"
                style={{ background: s.amber, color: s.bg }}
                onClick={handleSubmitQuiz}
                disabled={isLoading}
              >
                {isLoading ? '提交中...' : '提交答案'}
              </button>
            </div>
          )}

          {/* Free Q&A phase */}
          {phase === 'free_qa' && (
            <div>
              <h3 className="text-lg font-semibold mb-4" style={{ color: s.amber }}>
                自由问答
              </h3>
              <div className="flex flex-col gap-3 mb-4">
                {qaHistory.map((entry, i) => (
                  <div key={i}>
                    <div className="flex justify-end mb-1">
                      <div
                        className="rounded-2xl px-4 py-2 text-sm max-w-[80%]"
                        style={{ background: s.amber, color: s.bg }}
                      >
                        {entry.q}
                      </div>
                    </div>
                    <div className="flex justify-start">
                      <div
                        className="rounded-2xl px-4 py-2 text-sm max-w-[80%] leading-relaxed"
                        style={{ background: s.card, border: `1px solid ${s.border}` }}
                      >
                        {entry.a}
                      </div>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div
                      className="rounded-2xl px-4 py-2 text-sm opacity-50"
                      style={{ background: s.card, border: `1px solid ${s.border}` }}
                    >
                      思考中...
                    </div>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-xl px-4 py-2 text-sm outline-none"
                  style={{ background: s.card, border: `1px solid ${s.border}`, color: s.fg }}
                  placeholder="问老师任何问题..."
                  value={qaInput}
                  onChange={(e) => setQaInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleAsk()}
                  disabled={isLoading}
                />
                <button
                  className="px-4 py-2 rounded-xl font-medium disabled:opacity-40"
                  style={{ background: s.amber, color: s.bg }}
                  onClick={handleAsk}
                  disabled={isLoading || !qaInput.trim()}
                >
                  问
                </button>
              </div>
              <button
                className="mt-4 w-full py-2 rounded-xl text-sm opacity-60 transition-opacity hover:opacity-100"
                style={{ border: `1px solid ${s.border}` }}
                onClick={handleExit}
              >
                结束本节课
              </button>
            </div>
          )}
        </div>
      </main>
      <MobileNav />
    </div>
  )
}
