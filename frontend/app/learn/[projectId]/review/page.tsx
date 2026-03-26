'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL, glBtn } from '@/lib/learn-theme'

// ── Local types (mirrors backend Pydantic models) ─────────────────────────────

interface FsrsReviewItem {
  lesson_id: number
  q: string
  correct: string
  fsrs_state: Record<string, unknown>
}

interface FsrsReviewResponseItem {
  q: string
  lesson_id: number
  is_correct: boolean
  response_seconds: number
}

// ── Progress bar ──────────────────────────────────────────────────────────────

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total === 0 ? 0 : (current / total) * 100
  return (
    <div className="w-full h-1 rounded-full" style={{ background: 'rgba(201,168,76,0.1)' }}>
      <motion.div
        className="h-1 rounded-full"
        style={{ background: GL.amber }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      />
    </div>
  )
}

// ── Flashcard ─────────────────────────────────────────────────────────────────

function Flashcard({
  item,
  onAnswer,
}: {
  item: FsrsReviewItem
  onAnswer: (is_correct: boolean, response_seconds: number) => void
}) {
  const [revealed, setRevealed] = useState(false)
  const startRef = useRef<number>(Date.now())

  useEffect(() => {
    setRevealed(false)
    startRef.current = Date.now()
  }, [item])

  function handleReveal() {
    setRevealed(true)
  }

  function handleAnswer(is_correct: boolean) {
    const elapsed = (Date.now() - startRef.current) / 1000
    onAnswer(is_correct, elapsed)
  }

  return (
    <motion.div
      key={item.q}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.3 }}
      className="w-full max-w-lg mx-auto"
    >
      {/* Card face */}
      <div
        className="rounded-2xl p-8 border transition-all duration-300"
        style={{
          background: GL.card,
          borderColor: revealed ? GL.amber : GL.cardBorder,
          boxShadow: revealed ? '0 0 32px rgba(201,168,76,0.1)' : 'none',
          minHeight: 220,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 24,
        }}
      >
        {/* Question */}
        <p
          className="text-center text-lg leading-relaxed"
          style={{ fontFamily: 'Manrope, sans-serif', fontWeight: 500, color: GL.fg }}
        >
          {item.q}
        </p>

        {/* Divider */}
        {revealed && (
          <div className="w-full h-px" style={{ background: 'rgba(201,168,76,0.15)' }} />
        )}

        {/* Answer */}
        <AnimatePresence>
          {revealed && (
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className="text-center text-base leading-relaxed"
              style={{ fontFamily: 'Manrope, sans-serif', color: GL.amber }}
            >
              {item.correct}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Action buttons */}
      <div className="mt-6 flex flex-col items-center gap-3">
        {!revealed ? (
          <button
            onClick={handleReveal}
            className="w-full max-w-xs rounded-xl px-6 py-3 text-sm transition-all duration-200 border"
            style={{
              background: 'rgba(240,235,224,0.05)',
              borderColor: 'rgba(240,235,224,0.12)',
              color: GL.fg,
              fontFamily: 'Manrope, sans-serif',
              fontWeight: 500,
            }}
          >
            查看答案
          </button>
        ) : (
          <div className="flex gap-3 w-full max-w-xs">
            <button
              onClick={() => handleAnswer(false)}
              className="flex-1 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 border"
              style={{
                background: 'rgba(186,111,111,0.12)',
                borderColor: 'rgba(186,111,111,0.3)',
                color: '#e08080',
                fontFamily: 'Manrope, sans-serif',
              }}
            >
              没记住
            </button>
            <button
              onClick={() => handleAnswer(true)}
              className="flex-1 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200 border"
              style={{
                background: 'rgba(111,186,138,0.12)',
                borderColor: 'rgba(111,186,138,0.3)',
                color: '#6fba8a',
                fontFamily: 'Manrope, sans-serif',
              }}
            >
              记住了
            </button>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// ── Completion screen ─────────────────────────────────────────────────────────

function CompletionScreen({
  remembered,
  total,
  onBack,
}: {
  remembered: number
  total: number
  onBack: () => void
}) {
  const pct = total === 0 ? 0 : Math.round((remembered / total) * 100)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center gap-8 text-center"
    >
      <div
        className="w-24 h-24 rounded-full flex items-center justify-center text-4xl"
        style={{ background: 'rgba(201,168,76,0.08)', border: `1px solid ${GL.amber}` }}
      >
        {pct >= 80 ? '🏆' : pct >= 50 ? '📖' : '💪'}
      </div>
      <div>
        <p className="font-cormorant font-light text-3xl mb-2" style={{ color: GL.fg }}>
          复习完成
        </p>
        <p className="text-sm font-mono-dm" style={{ color: GL.fgMuted }}>
          记住了 {remembered} / {total} 张卡片（{pct}%）
        </p>
      </div>
      <button
        onClick={onBack}
        className="rounded-xl px-8 py-3 text-sm font-semibold transition-all duration-200"
        style={{ ...glBtn }}
      >
        返回仪表盘
      </button>
    </motion.div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const router = useRouter()

  const [items, setItems] = useState<FsrsReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [index, setIndex] = useState(0)
  const [responses, setResponses] = useState<FsrsReviewResponseItem[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`/api/learn/projects/${projectId}/review`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json() as Promise<{ items: FsrsReviewItem[]; count: number }>
      })
      .then(({ items: fetched }) => {
        setItems(fetched)
        setLoading(false)
      })
      .catch((err) => {
        setError(String(err))
        setLoading(false)
      })
  }, [projectId])

  async function handleAnswer(is_correct: boolean, response_seconds: number) {
    const item = items[index]
    const newResponses: FsrsReviewResponseItem[] = [
      ...responses,
      { q: item.q, lesson_id: item.lesson_id, is_correct, response_seconds },
    ]
    setResponses(newResponses)

    if (index + 1 < items.length) {
      setIndex(index + 1)
    } else {
      // All cards answered — submit
      setSubmitting(true)
      try {
        const res = await fetch(`/api/learn/projects/${projectId}/review/responses`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ responses: newResponses }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
      } catch (err) {
        _logger.error('Failed to submit review responses', err)
      } finally {
        setSubmitting(false)
        setDone(true)
      }
    }
  }

  const rememberedCount = responses.filter((r) => r.is_correct).length

  return (
    <div className="min-h-screen" style={{ background: GL.bg, color: GL.fg }}>
      <Header dark />
      <main className="max-w-2xl mx-auto px-6 py-10">
        {loading ? (
          <div className="flex items-center justify-center min-h-64">
            <motion.span
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1.6, repeat: Infinity }}
              className="font-mono-dm text-sm opacity-40"
            >
              载入中...
            </motion.span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-4 text-center min-h-64 justify-center">
            <p className="text-sm" style={{ color: 'rgba(186,111,111,0.8)', fontFamily: 'Manrope, sans-serif' }}>
              加载失败，请稍后重试
            </p>
            <button
              onClick={() => router.back()}
              className="text-sm font-mono-dm underline opacity-50 hover:opacity-80 transition-opacity"
            >
              返回
            </button>
          </div>
        ) : items.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center gap-6 text-center min-h-64 justify-center"
          >
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center text-2xl"
              style={{ background: 'rgba(201,168,76,0.08)', border: `1px solid ${GL.cardBorder}` }}
            >
              ✓
            </div>
            <div>
              <p className="font-cormorant font-light text-2xl mb-1">暂无需要复习的内容</p>
              <p className="text-sm font-mono-dm" style={{ color: GL.fgMuted }}>
                继续完成课程后这里会出现复习卡片
              </p>
            </div>
            <button
              onClick={() => router.push(`/learn/${projectId}`)}
              className="rounded-xl px-6 py-3 text-sm font-semibold transition-all duration-200"
              style={{ ...glBtn }}
            >
              返回仪表盘
            </button>
          </motion.div>
        ) : done ? (
          <div className="flex items-center justify-center min-h-64">
            <CompletionScreen
              remembered={rememberedCount}
              total={items.length}
              onBack={() => router.push(`/learn/${projectId}`)}
            />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header row */}
            <div className="flex items-center justify-between mb-2">
              <button
                onClick={() => router.push(`/learn/${projectId}`)}
                className="text-sm font-mono-dm opacity-40 hover:opacity-70 transition-opacity"
              >
                ← 返回
              </button>
              <span className="text-xs font-mono-dm" style={{ color: GL.fgMuted }}>
                {index + 1} / {items.length}
              </span>
            </div>

            <ProgressBar current={index} total={items.length} />

            <div className="pt-4">
              <AnimatePresence mode="wait">
                {!submitting && (
                  <Flashcard
                    key={`card-${index}`}
                    item={items[index]}
                    onAnswer={handleAnswer}
                  />
                )}
              </AnimatePresence>
              {submitting && (
                <div className="flex items-center justify-center min-h-48">
                  <motion.span
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.6, repeat: Infinity }}
                    className="font-mono-dm text-sm opacity-40"
                  >
                    保存中...
                  </motion.span>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
      <MobileNav />
    </div>
  )
}

// Minimal logger stub — avoids importing a heavy logging library
const _logger = {
  error: (...args: unknown[]) => console.error(...args),
}
