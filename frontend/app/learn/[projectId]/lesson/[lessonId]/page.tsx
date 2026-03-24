'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { useGeneralLesson } from '@/hooks/useGeneralLesson'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL, glBtn, glBtnDisabled } from '@/lib/learn-theme'

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

  const phaseLabel =
    phase === 'reading' ? '精读' : phase === 'quiz' ? '测验' : phase === 'free_qa' ? '问答' : phase

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
            {/* Golden ring */}
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

      {/* Lesson status bar */}
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
          {phaseLabel}
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
                    <span
                      className="dot1 w-1.5 h-1.5 rounded-full inline-block"
                      style={{ background: GL.amber }}
                    />
                    <span
                      className="dot2 w-1.5 h-1.5 rounded-full inline-block"
                      style={{ background: GL.amber }}
                    />
                    <span
                      className="dot3 w-1.5 h-1.5 rounded-full inline-block"
                      style={{ background: GL.amber }}
                    />
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
                <div
                  key={q.q}
                  className="rounded-2xl p-5"
                  style={{ background: GL.card, border: `1px solid ${GL.cardBorder}` }}
                >
                  <p
                    className="text-sm mb-3 font-medium"
                    style={{ color: GL.fg, fontFamily: 'Manrope, sans-serif' }}
                  >
                    <span style={{ color: GL.amber }} className="font-mono-dm mr-2">
                      {i + 1}.
                    </span>
                    {q.q}
                  </p>
                  <input
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
                    style={{
                      background: GL.inputBg,
                      border: `1px solid ${GL.inputBorder}`,
                      color: GL.fg,
                      fontFamily: 'Manrope, sans-serif',
                    }}
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
              className="w-full py-4 rounded-xl font-medium transition-all disabled:opacity-30"
              style={isLoading ? glBtnDisabled : glBtn}
              onClick={handleSubmitQuiz}
              disabled={isLoading}
            >
              {isLoading ? '提交中...' : '提交答案 →'}
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
                      <span
                        className="dot1 w-1.5 h-1.5 rounded-full inline-block"
                        style={{ background: GL.amber }}
                      />
                      <span
                        className="dot2 w-1.5 h-1.5 rounded-full inline-block"
                        style={{ background: GL.amber }}
                      />
                      <span
                        className="dot3 w-1.5 h-1.5 rounded-full inline-block"
                        style={{ background: GL.amber }}
                      />
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
