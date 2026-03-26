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
import { GL, glBtn, glBtnDisabled } from '@/lib/learn-theme'

// ── Retry hint banner ────────────────────────────────────────────────────────

function RetryHintBanner({ hints }: { hints: RetryHintItem[] }) {
  const [open, setOpen] = useState(false)
  if (!hints.length) return null
  return (
    <div
      className="rounded-2xl mb-5 overflow-hidden"
      style={{ background: 'rgba(201,168,76,0.06)', border: `1px solid rgba(201,168,76,0.25)` }}
    >
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium"
        style={{ color: GL.amber, fontFamily: 'Manrope, sans-serif' }}
        onClick={() => setOpen((v) => !v)}
      >
        <span>⚠ 上次答错了 {hints.length} 题，重点回顾一下</span>
        <span className="text-xs opacity-60 font-mono-dm">{open ? '收起 ↑' : '展开 ↓'}</span>
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
                <div key={i} className="text-sm" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  <p style={{ color: GL.fg, opacity: 0.7 }}>{h.question}</p>
                  <p className="mt-1 font-medium" style={{ color: GL.amber }}>
                    正确答案：{h.correct_answer}
                  </p>
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
    <div
      className="rounded-2xl p-5"
      style={{ background: GL.card, border: `1px solid ${GL.cardBorder}` }}
    >
      <p
        className="text-sm mb-4 font-medium leading-relaxed"
        style={{ color: GL.fg, fontFamily: 'Manrope, sans-serif' }}
      >
        <span style={{ color: GL.amber }} className="font-mono-dm mr-2">
          {index + 1}.
        </span>
        {question.question}
      </p>
      <div className="flex flex-col gap-2">
        {question.answerOptions.map((opt, j) => {
          const chosen = selected === j
          return (
            <button
              key={j}
              className="w-full text-left rounded-xl px-4 py-3 text-sm transition-all"
              style={{
                fontFamily: 'Manrope, sans-serif',
                background: chosen ? 'rgba(201,168,76,0.12)' : GL.inputBg,
                border: `1px solid ${chosen ? 'rgba(201,168,76,0.5)' : GL.inputBorder}`,
                color: chosen ? GL.amber : GL.fg,
              }}
              onClick={() => onSelect(j)}
            >
              <span className="font-mono-dm mr-2 opacity-50">
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
        <div
          className="inline-flex items-center justify-center w-20 h-20 rounded-full mb-3"
          style={{
            background: passed ? 'rgba(201,168,76,0.1)' : 'rgba(220,60,60,0.08)',
            border: `2px solid ${passed ? 'rgba(201,168,76,0.4)' : 'rgba(220,60,60,0.3)'}`,
          }}
        >
          <span
            className="font-cormorant font-light"
            style={{ fontSize: '1.8rem', color: passed ? GL.amber : '#e05555' }}
          >
            {pct}%
          </span>
        </div>
        <p className="text-sm opacity-50" style={{ fontFamily: 'Manrope, sans-serif' }}>
          {result.score}/{result.total} 正确 · {passed ? '通过' : '需要加强'}
        </p>
      </div>

      {/* Per-question breakdown */}
      <div className="flex flex-col gap-3 mb-6">
        {result.details.map((d: QuizDetail, i: number) => (
          <div
            key={i}
            className="rounded-2xl overflow-hidden"
            style={{ background: GL.card, border: `1px solid ${GL.cardBorder}` }}
          >
            <button
              className="w-full flex items-center gap-3 px-5 py-4 text-sm text-left"
              style={{ fontFamily: 'Manrope, sans-serif' }}
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
            >
              <span
                className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold"
                style={{
                  background: d.is_correct ? 'rgba(80,200,120,0.15)' : 'rgba(220,60,60,0.12)',
                  color: d.is_correct ? '#50c878' : '#e05555',
                }}
              >
                {d.is_correct ? '✓' : '✗'}
              </span>
              <span className="flex-1 leading-snug" style={{ color: GL.fg, opacity: 0.85 }}>
                {d.question}
              </span>
              <span className="text-xs opacity-30 font-mono-dm">{expandedIdx === i ? '↑' : '↓'}</span>
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
                        ? 'rgba(80,200,120,0.08)'
                        : isStudent
                          ? 'rgba(220,60,60,0.08)'
                          : 'transparent'
                      const border = isCorrect
                        ? 'rgba(80,200,120,0.3)'
                        : isStudent
                          ? 'rgba(220,60,60,0.25)'
                          : 'transparent'
                      return (
                        <div
                          key={j}
                          className="rounded-xl px-4 py-3 text-xs leading-relaxed"
                          style={{
                            background: bg,
                            border: `1px solid ${border}`,
                            fontFamily: 'Manrope, sans-serif',
                            color: GL.fg,
                            opacity: isCorrect || isStudent ? 1 : 0.45,
                          }}
                        >
                          <span className="font-mono-dm mr-1.5 opacity-50">
                            {String.fromCharCode(65 + j)}.
                          </span>
                          <span>{opt.text}</span>
                          {opt.rationale && (
                            <p className="mt-1.5 opacity-60 leading-relaxed">{opt.rationale}</p>
                          )}
                          {isCorrect && (
                            <span className="ml-2 text-xs" style={{ color: '#50c878' }}>
                              ✓ 正确答案
                            </span>
                          )}
                          {isStudent && !isCorrect && (
                            <span className="ml-2 text-xs" style={{ color: '#e05555' }}>
                              ✗ 你的答案
                            </span>
                          )}
                        </div>
                      )
                    })}
                    {d.hint && (
                      <p
                        className="text-xs px-1 opacity-50 leading-relaxed"
                        style={{ fontFamily: 'Manrope, sans-serif', color: GL.fg }}
                      >
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
        className="w-full py-4 rounded-xl font-medium transition-all"
        style={glBtn}
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

  // selectedAnswers[i] = index into question[i].answerOptions, or null
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
    // Send integer indices; unanswered questions send null
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
      <div className="min-h-screen flex flex-col" style={{ background: GL.bg, color: GL.fg }}>
        <Header dark />
        <main className="flex-1 flex flex-col items-center justify-center px-6 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 180, damping: 16 }}
            className="space-y-6"
          >
            <div className="relative w-24 h-24 mx-auto">
              {[0, 1].map((i) => (
                <motion.div
                  key={i}
                  className="absolute inset-0 rounded-full border"
                  style={{ borderColor: 'rgba(201,168,76,0.4)' }}
                  initial={{ scale: 0.8, opacity: 1 }}
                  animate={{ scale: 2, opacity: 0 }}
                  transition={{ duration: 1.6, delay: i * 0.6, repeat: Infinity, ease: 'easeOut' }}
                />
              ))}
              <div
                className="absolute inset-0 rounded-full flex items-center justify-center text-3xl"
                style={{ background: 'rgba(201,168,76,0.1)', border: `1px solid ${GL.cardBorder}` }}
              >
                ✦
              </div>
            </div>
            <div>
              <h2
                className="font-cormorant font-light"
                style={{ fontSize: '2.5rem', color: GL.amber }}
              >
                课程完成
              </h2>
              <p className="mt-2 text-sm opacity-50" style={{ fontFamily: 'Manrope, sans-serif' }}>
                你已完成本节课的学习
              </p>
            </div>
            <button
              className="px-8 py-3 rounded-xl font-medium transition-all"
              style={glBtn}
              onClick={() => router.push(`/learn/${projectId}`)}
            >
              返回课程地图
            </button>
          </motion.div>
        </main>
        <MobileNav />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: GL.bg, color: GL.fg }}>
      <Header dark />

      {/* Status bar */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ borderColor: GL.navBorder }}
      >
        <span
          className="text-sm font-medium truncate max-w-xs"
          style={{ color: GL.fg, fontFamily: 'Manrope, sans-serif' }}
        >
          {lessonTitle || '正在加载...'}
        </span>
        <span
          className="text-xs font-mono-dm tracking-widest uppercase px-3 py-1 rounded-full flex-shrink-0"
          style={{
            color: GL.amber,
            background: GL.amberFaint,
            border: `1px solid rgba(201,168,76,0.2)`,
          }}
        >
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

            <div className="mb-3 flex items-center gap-2">
              <span
                className="text-xs font-mono-dm tracking-widest uppercase"
                style={{ color: GL.amberMuted }}
              >
                学习材料
              </span>
            </div>
            <div
              className="rounded-2xl p-6 text-sm leading-relaxed whitespace-pre-wrap mb-6"
              style={{
                background: GL.card,
                border: `1px solid ${GL.cardBorder}`,
                color: GL.fg,
                fontFamily: 'Manrope, sans-serif',
                lineHeight: 1.9,
              }}
            >
              {studyGuide || (
                <div className="flex items-center gap-3 opacity-40">
                  <div className="flex gap-1">
                    {[1, 2, 3].map((k) => (
                      <span
                        key={k}
                        className="w-1.5 h-1.5 rounded-full inline-block"
                        style={{ background: GL.amber }}
                      />
                    ))}
                  </div>
                  <span style={{ fontFamily: 'Manrope, sans-serif' }}>正在加载学习材料...</span>
                </div>
              )}
            </div>
            <button
              className="w-full py-4 rounded-xl font-medium transition-all disabled:opacity-30"
              style={isLoading || !studyGuide ? glBtnDisabled : glBtn}
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
              <span
                className="text-xs font-mono-dm tracking-widest uppercase"
                style={{ color: GL.amberMuted }}
              >
                随堂测验
              </span>
              <h3
                className="font-cormorant font-light mt-1"
                style={{ fontSize: '1.8rem', color: GL.fg }}
              >
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
              className="w-full py-4 rounded-xl font-medium transition-all disabled:opacity-30"
              style={isLoading ? glBtnDisabled : glBtn}
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
            <p className="text-sm opacity-50 mb-6" style={{ fontFamily: 'Manrope, sans-serif' }}>
              测验题目正在更新中，跳过本次测验
            </p>
            <button
              className="px-8 py-3 rounded-xl font-medium transition-all"
              style={glBtn}
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
              <span
                className="text-xs font-mono-dm tracking-widest uppercase"
                style={{ color: GL.amberMuted }}
              >
                自由问答
              </span>
              <h3
                className="font-cormorant font-light mt-1"
                style={{ fontSize: '1.8rem', color: GL.fg }}
              >
                问老师任何问题
              </h3>
            </div>

            <div className="flex flex-col gap-4 mb-4">
              {qaHistory.map((entry) => (
                <div key={entry.id} className="space-y-2">
                  <div className="flex justify-end">
                    <div
                      className="rounded-2xl px-4 py-3 text-sm max-w-[80%]"
                      style={{
                        background: `linear-gradient(135deg, ${GL.amber}, #e8c96a)`,
                        color: '#0f0d1a',
                        fontFamily: 'Manrope, sans-serif',
                        fontWeight: 500,
                      }}
                    >
                      {entry.q}
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div
                      className="w-6 h-6 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center text-xs"
                      style={{
                        background: 'rgba(201,168,76,0.15)',
                        border: `1px solid ${GL.cardBorder}`,
                        color: GL.amber,
                      }}
                    >
                      ✦
                    </div>
                    <div
                      className="rounded-2xl px-4 py-3 text-sm max-w-[80%] leading-relaxed"
                      style={{
                        background: GL.card,
                        border: `1px solid ${GL.cardBorder}`,
                        color: GL.fg,
                        fontFamily: 'Manrope, sans-serif',
                      }}
                    >
                      {entry.a}
                    </div>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex items-start gap-2">
                  <div
                    className="w-6 h-6 rounded-full flex-shrink-0 mt-0.5 flex items-center justify-center text-xs"
                    style={{
                      background: 'rgba(201,168,76,0.15)',
                      border: `1px solid ${GL.cardBorder}`,
                      color: GL.amber,
                    }}
                  >
                    ✦
                  </div>
                  <div
                    className="rounded-2xl px-4 py-3 text-sm"
                    style={{ background: GL.card, border: `1px solid ${GL.cardBorder}` }}
                  >
                    <div className="flex gap-1 items-center opacity-50">
                      {[1, 2, 3].map((k) => (
                        <span
                          key={k}
                          className="w-1.5 h-1.5 rounded-full inline-block"
                          style={{ background: GL.amber }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2 mb-3">
              <input
                className="flex-1 rounded-xl px-4 py-3 text-sm outline-none transition-all"
                style={{
                  background: GL.inputBg,
                  border: `1px solid ${GL.inputBorder}`,
                  color: GL.fg,
                  fontFamily: 'Manrope, sans-serif',
                }}
                placeholder="问老师任何问题..."
                value={qaInput}
                onChange={(e) => setQaInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleAsk()}
                disabled={isLoading}
              />
              <button
                className="px-4 py-2 rounded-xl font-medium transition-all disabled:opacity-30"
                style={qaInput.trim() ? glBtn : glBtnDisabled}
                onClick={handleAsk}
                disabled={isLoading || !qaInput.trim()}
              >
                问
              </button>
            </div>
            <button
              className="w-full py-3 rounded-xl text-sm transition-opacity hover:opacity-80"
              style={{
                border: `1px solid rgba(240,235,224,0.1)`,
                color: 'rgba(240,235,224,0.4)',
                fontFamily: 'Manrope, sans-serif',
              }}
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
