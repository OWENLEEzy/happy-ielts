'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  useGeneralLesson,
  type RetryHintItem,
  type QuizQuestion,
  type QuizDetail,
  type QuizResult,
} from '@/hooks/useGeneralLesson'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { DogAvatar } from '@/components/DogAvatar'

// ── Retry hint banner ────────────────────────────────────────────────────────

function RetryHintBanner({ hints }: { hints: RetryHintItem[] }) {
  const [open, setOpen] = useState(false)
  if (!hints.length) return null
  return (
    <div className="rounded-xl mb-5 overflow-hidden bg-error/5 border border-error/10">
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-error"
        onClick={() => setOpen((v) => !v)}
      >
        <span>⚠ 上次答错了 {hints.length} 题，重点回顾一下</span>
        <span className="text-xs text-error/50 font-label">{open ? '收起 ↑' : '展开 ↓'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="px-5 pb-5 flex flex-col gap-3">
              {hints.map((h, i) => (
                <div key={i} className="text-sm font-body">
                  <p className="text-on-surface-variant">{h.question}</p>
                  <p className="mt-1 font-medium text-primary">正确答案：{h.correct_answer}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Multiple-choice quiz ─────────────────────────────────────────────────────

function QuizCard({
  question,
  index,
  selected,
  onSelect,
}: {
  question: QuizQuestion
  index: number
  selected: number | null
  onSelect: (idx: number) => void
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-5 shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)]">
      <p className="text-sm mb-4 font-body text-on-surface font-medium leading-relaxed">
        <span className="font-black font-label text-primary mr-2">{index + 1}.</span>
        {question.question}
      </p>
      <div className="flex flex-col gap-2">
        {question.answerOptions.map((opt, j) => {
          const chosen = selected === j
          return (
            <button
              key={j}
              className={`w-full text-left rounded-lg px-4 py-3 text-sm font-body border-2 transition-all ${
                chosen
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-outline-variant/20 bg-surface-container-low text-on-surface hover:border-primary/30'
              }`}
              onClick={() => onSelect(j)}
            >
              <span className="font-black font-label text-on-surface-variant/50 mr-2">
                {String.fromCharCode(65 + j)}.
              </span>
              {opt.text}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Quiz result view ─────────────────────────────────────────────────────────

function QuizResultView({
  result,
  onContinue,
}: {
  result: QuizResult
  onContinue: () => void
}) {
  const pct = result.total > 0 ? Math.round((result.score / result.total) * 100) : 0
  const passed = pct >= 60
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Score header */}
      <div className="text-center mb-6">
        <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full mb-3 ${
          passed
            ? 'bg-primary-container/30 border-2 border-primary/30'
            : 'bg-error/10 border-2 border-error/20'
        }`}>
          <span className={`text-3xl font-extrabold font-headline ${passed ? 'text-primary' : 'text-error'}`}>
            {pct}%
          </span>
        </div>
        <p className="text-sm text-on-surface-variant font-body">
          {result.score}/{result.total} 正确 · {passed ? '通过' : '需要加强'}
        </p>
      </div>

      {/* Per-question breakdown */}
      <div className="flex flex-col gap-3 mb-6">
        {result.details.map((d: QuizDetail, i: number) => (
          <div
            key={i}
            className="rounded-xl overflow-hidden bg-surface-container-lowest shadow-[0_1px_6px_color-mix(in_srgb,var(--primary)_4%,transparent)]"
          >
            <button
              className="w-full flex items-center gap-3 px-5 py-4 text-sm text-left"
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
            >
              <span className={`w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
                d.is_correct ? 'bg-primary/10 text-primary' : 'bg-error/10 text-error'
              }`}>
                {d.is_correct ? '✓' : '✗'}
              </span>
              <span className="flex-1 leading-snug text-on-surface font-body">{d.question}</span>
              <span className="text-xs text-on-surface-variant/40 font-label">{expandedIdx === i ? '↑' : '↓'}</span>
            </button>
            <AnimatePresence>
              {expandedIdx === i && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="px-5 pb-4 flex flex-col gap-2">
                    {d.options.map((opt, j) => {
                      const isStudent = j === d.student_answer_index
                      const isCorrect = j === d.correct_answer_index
                      const bg = isCorrect
                        ? 'bg-primary/5 border-primary/15'
                        : isStudent
                          ? 'bg-error/5 border-error/10'
                          : 'bg-transparent border-transparent'
                      return (
                        <div
                          key={j}
                          className={`rounded-lg px-4 py-3 text-xs leading-relaxed border font-body text-on-surface ${bg} ${
                            isCorrect || isStudent ? 'opacity-100' : 'opacity-40'
                          }`}
                        >
                          <span className="font-label text-on-surface-variant/50 mr-1.5">
                            {String.fromCharCode(65 + j)}.
                          </span>
                          <span>{opt.text}</span>
                          {opt.rationale && (
                            <p className="mt-1.5 text-on-surface-variant/60 leading-relaxed">{opt.rationale}</p>
                          )}
                          {isCorrect && (
                            <span className="ml-2 text-xs text-primary font-label">✓ 正确答案</span>
                          )}
                          {isStudent && !isCorrect && (
                            <span className="ml-2 text-xs text-error font-label">✗ 你的答案</span>
                          )}
                        </div>
                      )
                    })}
                    {d.hint && (
                      <p className="text-xs px-1 text-on-surface-variant/50 leading-relaxed font-body">
                        💡 {d.hint}
                      </p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>

      <button
        className="w-full signature-gradient text-white py-3.5 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
        onClick={onContinue}
      >
        继续 →
      </button>
    </motion.div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function LessonPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = Number(params.projectId)
  const lessonId = Number(params.lessonId)
  const {
    phase,
    studyGuide,
    lessonTitle,
    retryHint,
    quiz,
    quizResult,
    qaHistory,
    start,
    sendAction,
    abort,
  } = useGeneralLesson(projectId, lessonId)

  const [selectedAnswers, setSelectedAnswers] = useState<(number | null)[]>([])
  const [qaInput, setQaInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    start()
    return () => abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (quiz.length) setSelectedAnswers(Array(quiz.length).fill(null))
  }, [quiz])

  const handleNext = async () => {
    setIsLoading(true)
    await sendAction({ type: 'next' })
    setIsLoading(false)
  }

  const handleSubmitQuiz = async () => {
    setIsLoading(true)
    await sendAction({ type: 'answers', answers: selectedAnswers })
    setIsLoading(false)
  }

  const handleContinueAfterResult = async () => {
    setIsLoading(true)
    await sendAction({ type: 'next' })
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

  const phaseLabel: Record<string, string> = {
    reading: '精读',
    quiz: '测验',
    quiz_result: '结果',
    quiz_skipped: '测验',
    free_qa: '问答',
    done: '完成',
  }

  if (phase === 'done') {
    return (
      <div className="min-h-screen flex flex-col bg-background">
        <Header />
        <main className="flex-1 flex flex-col items-center justify-center px-6 text-center">
          <div className="flex flex-col items-center gap-6">
            <div className="w-24 h-24 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-4xl shadow-[0_0_32px_color-mix(in_srgb,var(--primary)_15%,transparent)]">
              ✓
            </div>
            <div>
              <h2 className="text-2xl font-extrabold font-headline text-primary mb-2">课程完成</h2>
              <p className="text-sm text-on-surface-variant font-body">你已完成本节课的学习</p>
            </div>
            <button
              className="signature-gradient text-white px-8 py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
              onClick={() => router.push(`/learn/${projectId}`)}
            >
              返回课程地图
            </button>
          </div>
        </main>
        <MobileNav />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      {/* Status bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-outline-variant/20">
        <span className="text-sm font-medium font-body text-on-surface truncate max-w-xs">
          {lessonTitle || '正在加载...'}
        </span>
        <span className="text-xs font-bold font-label px-3 py-1 rounded-full bg-primary/10 text-primary flex-shrink-0">
          {phaseLabel[phase] ?? phase}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-2xl w-full mx-auto">
        {/* Reading phase */}
        {phase === 'reading' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <RetryHintBanner hints={retryHint} />

            <div className="mb-3">
              <span className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
                学习材料
              </span>
            </div>
            <div className="bg-surface-container-lowest rounded-xl p-6 text-sm leading-relaxed whitespace-pre-wrap mb-6 font-body text-on-surface shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)]">
              {studyGuide || (
                <span className="text-on-surface-variant/40">正在加载学习材料...</span>
              )}
            </div>
            <button
              className="w-full signature-gradient text-white py-3.5 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-40 disabled:hover:scale-100"
              onClick={handleNext}
              disabled={isLoading || !studyGuide}
            >
              {isLoading ? '请稍候...' : '继续 →'}
            </button>
          </motion.div>
        )}

        {/* Quiz phase */}
        {phase === 'quiz' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="mb-5">
              <span className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
                随堂测验
              </span>
              <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">
                检验一下你的理解
              </h3>
            </div>
            <div className="flex flex-col gap-4 mb-6">
              {quiz.map((q, i) => (
                <QuizCard
                  key={i}
                  question={q}
                  index={i}
                  selected={selectedAnswers[i] ?? null}
                  onSelect={(idx) =>
                    setSelectedAnswers((prev) => {
                      const next = [...prev]
                      next[i] = idx
                      return next
                    })
                  }
                />
              ))}
            </div>
            <button
              className="w-full signature-gradient text-white py-3.5 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-40 disabled:hover:scale-100"
              onClick={handleSubmitQuiz}
              disabled={isLoading}
            >
              {isLoading ? '提交中...' : '提交答案 →'}
            </button>
          </motion.div>
        )}

        {/* Quiz result phase */}
        {phase === 'quiz_result' && quizResult && (
          <QuizResultView result={quizResult} onContinue={handleContinueAfterResult} />
        )}

        {/* Quiz skipped */}
        {phase === 'quiz_skipped' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-12"
          >
            <p className="text-sm text-on-surface-variant font-body mb-6">
              测验题目正在更新中，跳过本次测验
            </p>
            <button
              className="signature-gradient text-white px-8 py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
              onClick={handleContinueAfterResult}
            >
              继续 →
            </button>
          </motion.div>
        )}

        {/* Free Q&A phase */}
        {phase === 'free_qa' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col h-full"
          >
            <div className="mb-5">
              <span className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
                自由问答
              </span>
              <h3 className="text-2xl font-extrabold font-headline text-on-surface mt-1">
                问老师任何问题
              </h3>
            </div>

            <div className="flex flex-col gap-4 mb-4">
              {qaHistory.map((entry) => (
                <div key={entry.id} className="space-y-2">
                  <div className="flex justify-end">
                    <div className="signature-gradient text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-[80%] text-sm font-body">
                      {entry.q}
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="flex-shrink-0 mt-0.5">
                      <DogAvatar role="teacher" size={28} emphasis="inline" alt="Professor 金毛" />
                    </div>
                    <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] text-sm font-body text-on-surface leading-relaxed">
                      {entry.a}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex items-start gap-2">
                  <div className="flex-shrink-0 mt-0.5">
                    <DogAvatar role="teacher" size={28} emphasis="inline" alt="Professor 金毛" />
                  </div>
                  <div className="bg-surface-container-lowest border border-outline-variant/20 rounded-2xl rounded-bl-sm px-4 py-3">
                    <div className="flex gap-1 items-center">
                      {[1, 2, 3].map((k) => (
                        <span key={k} className="w-1.5 h-1.5 bg-primary rounded-full inline-block opacity-50" />
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2 mb-3">
              <input
                className="flex-1 rounded-xl border border-outline-variant/20 bg-surface-container-low px-4 py-3 text-sm font-body text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-on-surface-variant/40"
                placeholder="问老师任何问题..."
                value={qaInput}
                onChange={(e) => setQaInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleAsk()}
                disabled={isLoading}
              />
              <button
                className="signature-gradient text-white px-4 py-2 rounded-xl font-bold text-sm font-label shadow shadow-primary/25 hover:scale-105 transition-transform disabled:opacity-40 disabled:hover:scale-100"
                onClick={handleAsk}
                disabled={isLoading || !qaInput.trim()}
              >
                问
              </button>
            </div>
            <button
              className="w-full py-3 rounded-xl text-sm font-body text-on-surface-variant border border-outline-variant/20 hover:bg-surface-container-low transition-colors"
              onClick={handleExit}
            >
              结束本节课
            </button>
          </motion.div>
        )}
      </div>

      <MobileNav />
    </div>
  )
}
