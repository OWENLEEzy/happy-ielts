'use client'
import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'

// ── Local types ──────────────────────────────────────────────────────────────

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

// ── Progress bar ─────────────────────────────────────────────────────────────

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total === 0 ? 0 : (current / total) * 100
  return (
    <div className="w-full h-1.5 bg-primary-container/20 rounded-full overflow-hidden">
      <motion.div
        className="h-full rounded-full bg-primary"
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      />
    </div>
  )
}

// ── Flashcard ────────────────────────────────────────────────────────────────

function Flashcard({
  item,
  onAnswer,
}: {
  item: FsrsReviewItem
  onAnswer: (is_correct: boolean, response_seconds: number) => void
}) {
  const [revealed, setRevealed] = useState(false)
  const startRef = useRef<number>(0)
  useEffect(() => {
    startRef.current = Date.now()
  }, [])

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
      {/* Card */}
      <div className={`rounded-xl p-8 shadow-[0_4px_20px_color-mix(in_srgb,var(--primary)_8%,transparent)] transition-all duration-300 ${
        revealed
          ? 'bg-primary-container/15 border-2 border-primary/20'
          : 'bg-surface-container-lowest border border-outline-variant/20'
      }`}
        style={{ minHeight: 220, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24 }}
      >
        {/* Question */}
        <p className="text-center text-lg font-body font-medium text-on-surface leading-relaxed">
          {item.q}
        </p>

        {/* Divider */}
        {revealed && <div className="w-full h-px bg-primary/10" />}

        {/* Answer */}
        <AnimatePresence>
          {revealed && (
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }}
              className="text-center text-base font-body font-semibold text-primary leading-relaxed"
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
            className="w-full max-w-xs signature-gradient text-white px-6 py-3 rounded-full font-bold text-sm font-label shadow shadow-primary/25 hover:scale-105 transition-transform"
          >
            查看答案
          </button>
        ) : (
          <div className="flex gap-3 w-full max-w-xs">
            <button
              onClick={() => handleAnswer(false)}
              className="flex-1 rounded-full px-4 py-3 text-sm font-bold font-label bg-error/10 text-error border border-error/20 hover:bg-error/15 transition-colors"
            >
              ✗ 没记住
            </button>
            <button
              onClick={() => handleAnswer(true)}
              className="flex-1 rounded-full px-4 py-3 text-sm font-bold font-label bg-primary/10 text-primary border border-primary/20 hover:bg-primary/15 transition-colors"
            >
              ✓ 记住了
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
      <div className="w-24 h-24 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-4xl shadow-[0_0_24px_color-mix(in_srgb,var(--primary)_12%,transparent)]">
        {pct >= 80 ? '🏆' : pct >= 50 ? '📖' : '💪'}
      </div>
      <div>
        <p className="text-2xl font-extrabold font-headline text-primary mb-2">复习完成！</p>
        <p className="text-sm text-on-surface-variant font-body">
          记住了 {remembered} / {total} 张卡片（{pct}%）
        </p>
      </div>
      <button
        onClick={onBack}
        className="signature-gradient text-white px-8 py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
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
      setSubmitting(true)
      try {
        const res = await fetch(`/api/learn/projects/${projectId}/review/responses`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ responses: newResponses }),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
      } catch (err) {
        console.error('Failed to submit review responses', err)
      } finally {
        setSubmitting(false)
        setDone(true)
      }
    }
  }

  const rememberedCount = responses.filter((r) => r.is_correct).length

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />
      <main className="max-w-2xl mx-auto px-6 py-10 w-full flex-1">
        {loading ? (
          <div className="flex items-center justify-center min-h-64">
            <div className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="w-2.5 h-2.5 bg-primary rounded-full inline-block"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.2 }}
                />
              ))}
            </div>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-4 text-center min-h-64 justify-center">
            <p className="text-sm text-error font-body">加载失败，请稍后重试</p>
            <button
              onClick={() => router.back()}
              className="text-sm font-label text-on-surface-variant underline opacity-50 hover:opacity-80 transition-opacity"
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
            <div className="w-16 h-16 rounded-full bg-primary/10 border border-outline-variant/20 flex items-center justify-center text-2xl">
              ✓
            </div>
            <div>
              <p className="text-xl font-extrabold font-headline text-on-surface mb-1">暂无需要复习的内容</p>
              <p className="text-sm text-on-surface-variant font-body">
                继续完成课程后这里会出现复习卡片
              </p>
            </div>
            <button
              onClick={() => router.push(`/learn/${projectId}`)}
              className="signature-gradient text-white px-6 py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform"
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
                className="text-sm font-label text-on-surface-variant/50 hover:text-on-surface-variant transition-colors"
              >
                ← 返回
              </button>
              <span className="text-xs font-label text-on-surface-variant">
                {index + 1} / {items.length}
              </span>
            </div>

            <ProgressBar current={index} total={items.length} />

            <div className="pt-4">
              <AnimatePresence mode="wait">
                {!submitting && (
                  <Flashcard key={`card-${index}`} item={items[index]} onAnswer={handleAnswer} />
                )}
              </AnimatePresence>
              {submitting && (
                <div className="flex items-center justify-center min-h-48">
                  <div className="flex gap-1.5">
                    {[0, 1, 2].map((i) => (
                      <motion.span
                        key={i}
                        className="w-2.5 h-2.5 bg-primary rounded-full inline-block"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.2 }}
                      />
                    ))}
                  </div>
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
