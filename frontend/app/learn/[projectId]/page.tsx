'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL } from '@/lib/learn-theme'
import { client } from '@/lib/client'
import type { components } from '@/types/api'

type Project = components['schemas']['ProjectDashboardResponse']
type DimensionState = components['schemas']['DimensionState']

function MasteryRing({ value, size = 48 }: { value: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const dash = circ * value
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgba(201,168,76,0.12)"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={GL.amber}
        strokeWidth={3}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 1s ease' }}
      />
      <text
        x={size / 2}
        y={size / 2 + 5}
        textAnchor="middle"
        fontSize={size < 40 ? 9 : 11}
        fontFamily="DM Mono, monospace"
        fill={GL.amber}
      >
        {Math.round(value * 100)}%
      </text>
    </svg>
  )
}

function TrendBadge({ trend }: { trend: DimensionState['trend'] }) {
  if (trend === 'improving') {
    return (
      <span className="text-xs font-mono-dm" style={{ color: '#6fba8a' }}>
        ↑ 进步中
      </span>
    )
  }
  if (trend === 'worsening') {
    return (
      <span className="text-xs font-mono-dm" style={{ color: '#ba6f6f' }}>
        ↓ 需加强
      </span>
    )
  }
  return (
    <span className="text-xs font-mono-dm" style={{ color: 'rgba(240,235,224,0.3)' }}>
      — 稳定
    </span>
  )
}

export default function ProjectDashboard() {
  const { projectId } = useParams<{ projectId: string }>()
  const router = useRouter()
  const [project, setProject] = useState<Project | null>(null)
  const [newlyUnlocked, setNewlyUnlocked] = useState<number | null>(null)
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const [fsrsDueCount, setFsrsDueCount] = useState(0)

  useEffect(() => {
    client
      .GET('/api/learn/projects/{project_id}/dashboard', {
        params: { path: { project_id: Number(projectId) } },
      })
      .then(({ data }) => {
        if (!data) return
        setProject(data)
        // Find first ready lesson to highlight
        for (const ch of data.chapters) {
          const first = ch.lessons.find((l) => l.status === 'ready')
          if (first) {
            setNewlyUnlocked(first.id)
            break
          }
        }
      })
      .catch(() => {})
  }, [projectId])

  // Fetch fsrs_due_count — API doesn't exist yet, silently fail
  useEffect(() => {
    fetch(`/api/learn/projects/${projectId}/review`)
      .then((res) => {
        if (!res.ok) return
        return res.json()
      })
      .then((data: unknown) => {
        if (
          data &&
          typeof data === 'object' &&
          'fsrs_due_count' in data &&
          typeof (data as Record<string, unknown>).fsrs_due_count === 'number'
        ) {
          setFsrsDueCount((data as { fsrs_due_count: number }).fsrs_due_count)
        }
      })
      .catch(() => {})
  }, [projectId])

  if (!project) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: GL.bg, color: GL.fg }}
      >
        <motion.div
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.6, repeat: Infinity }}
        >
          <span className="font-mono-dm text-sm opacity-40">载入中...</span>
        </motion.div>
      </div>
    )
  }

  // Chapters that have a worsening dimension with low mastery
  const worseningChapters = project.chapters
    .map((ch) => {
      const dim = project.dimensions[ch.title]
      return dim && dim.trend === 'worsening' && dim.mastery < 0.5 ? ch.title : null
    })
    .filter((t): t is string => t !== null)

  return (
    <div
      className="min-h-screen"
      style={{
        background: GL.bg,
        color: GL.fg,
      }}
    >
      <Header dark />

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-12">
        {/* Goal progress hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-end gap-8"
        >
          <div>
            <div
              className="text-xs font-mono-dm tracking-widest uppercase mb-2"
              style={{ color: 'rgba(201,168,76,0.6)' }}
            >
              学习目标
            </div>
            <h1
              className="font-cormorant font-light leading-tight"
              style={{ fontSize: 'clamp(1.8rem, 4vw, 3rem)' }}
            >
              {project.goal_outcome}
            </h1>

            {/* 开始复习 button — only shown when fsrs items are due */}
            {fsrsDueCount > 0 && (
              <motion.button
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                onClick={() => router.push(`/learn/${projectId}/review`)}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-mono-dm border transition-all duration-200"
                style={{
                  background: 'rgba(201,168,76,0.08)',
                  borderColor: 'rgba(201,168,76,0.3)',
                  color: GL.amber,
                }}
              >
                ⟳ 开始复习
                <span
                  className="px-1.5 py-0.5 rounded-full text-xs"
                  style={{ background: 'rgba(201,168,76,0.2)' }}
                >
                  {fsrsDueCount}
                </span>
              </motion.button>
            )}
          </div>
          <div className="flex-shrink-0 ml-auto">
            <MasteryRing value={project.goal_progress} size={80} />
          </div>
        </motion.div>

        {/* Worsening dimension warning banner */}
        <AnimatePresence>
          {!bannerDismissed && worseningChapters.length > 0 && (
            <motion.div
              key="worsening-banner"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25 }}
              className="flex items-start gap-3 rounded-xl px-4 py-3 border"
              style={{
                background: 'rgba(180,120,40,0.06)',
                borderColor: 'rgba(180,120,40,0.3)',
              }}
            >
              <span className="flex-1 text-sm font-mono-dm" style={{ color: '#d4a24a' }}>
                ⚠{' '}
                {worseningChapters.map((name, i) => (
                  <span key={name}>
                    {i > 0 && '、'}「{name}」
                  </span>
                ))}{' '}
                掌握度偏低，建议优先完成该章节
              </span>
              <button
                onClick={() => setBannerDismissed(true)}
                className="text-xs font-mono-dm opacity-40 hover:opacity-70 transition-opacity flex-shrink-0 mt-0.5"
                style={{ color: '#d4a24a' }}
                aria-label="关闭提示"
              >
                ✕
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Chapters + lessons */}
        <section className="space-y-8">
          <h2
            className="text-xs font-mono-dm tracking-widest uppercase"
            style={{ color: 'rgba(201,168,76,0.5)' }}
          >
            课程地图
          </h2>

          {project.chapters.map((ch, ci) => {
            const dim: DimensionState | undefined = project.dimensions[ch.title]

            return (
              <motion.div
                key={ch.title}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + ci * 0.08 }}
              >
                {/* Chapter header with inline dimension state */}
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className="text-xs font-mono-dm tracking-widest uppercase"
                    style={{ color: 'rgba(240,235,224,0.35)' }}
                  >
                    Chapter {ci + 1} · {ch.title}
                  </div>

                  {dim && (
                    <>
                      <MasteryRing value={dim.mastery} size={28} />
                      <TrendBadge trend={dim.trend} />
                      <span
                        className="text-xs font-mono-dm"
                        style={{ color: 'rgba(240,235,224,0.25)' }}
                      >
                        {dim.sessions} 次练习
                      </span>
                    </>
                  )}
                </div>

                <div className="space-y-2">
                  {ch.lessons.map((lesson) => {
                    const isNew = lesson.id === newlyUnlocked
                    const isReady = lesson.status === 'ready'

                    return (
                      <AnimatePresence key={lesson.id}>
                        <motion.div
                          layout
                          initial={isNew ? { scale: 0.95, opacity: 0 } : false}
                          animate={{ scale: 1, opacity: 1 }}
                          transition={
                            isNew ? { type: 'spring', stiffness: 180, damping: 16 } : undefined
                          }
                        >
                          <button
                            disabled={!isReady}
                            onClick={() =>
                              isReady && router.push(`/learn/${projectId}/lesson/${lesson.id}`)
                            }
                            className="w-full text-left rounded-xl px-5 py-4 flex items-center gap-4 transition-all duration-300 border group"
                            style={{
                              background: isNew
                                ? 'linear-gradient(135deg, rgba(201,168,76,0.12), rgba(201,168,76,0.04))'
                                : isReady
                                  ? 'rgba(240,235,224,0.03)'
                                  : 'rgba(240,235,224,0.01)',
                              borderColor: isNew
                                ? 'rgba(201,168,76,0.35)'
                                : isReady
                                  ? 'rgba(240,235,224,0.08)'
                                  : 'rgba(240,235,224,0.04)',
                              cursor: isReady ? 'pointer' : 'not-allowed',
                              boxShadow: isNew ? '0 0 24px rgba(201,168,76,0.12)' : 'none',
                            }}
                          >
                            {/* Status dot */}
                            <div
                              className="w-2 h-2 rounded-full flex-shrink-0 transition-all duration-500"
                              style={{
                                background: isNew
                                  ? GL.amber
                                  : isReady
                                    ? 'rgba(201,168,76,0.5)'
                                    : 'rgba(240,235,224,0.12)',
                                boxShadow: isNew ? '0 0 8px #c9a84c' : 'none',
                              }}
                            />

                            {/* Title */}
                            <span
                              className="flex-1 text-sm"
                              style={{
                                fontFamily: 'Manrope, sans-serif',
                                fontWeight: isReady ? 500 : 400,
                                color: isReady ? GL.fg : 'rgba(240,235,224,0.3)',
                              }}
                            >
                              {lesson.title}
                            </span>

                            {/* Newly unlocked badge */}
                            {isNew && (
                              <motion.span
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: 'spring', stiffness: 300, delay: 0.3 }}
                                className="text-xs px-2.5 py-1 rounded-full font-mono-dm"
                                style={{ background: 'rgba(201,168,76,0.2)', color: GL.amber }}
                              >
                                新解锁
                              </motion.span>
                            )}

                            {/* Arrow */}
                            {isReady && !isNew && (
                              <span className="text-xs opacity-0 group-hover:opacity-40 transition-opacity font-mono-dm">
                                →
                              </span>
                            )}

                            {/* Pending lock */}
                            {!isReady && (
                              <span
                                className="text-xs font-mono-dm"
                                style={{ color: 'rgba(240,235,224,0.15)' }}
                              >
                                准备中
                              </span>
                            )}
                          </button>
                        </motion.div>
                      </AnimatePresence>
                    )
                  })}
                </div>
              </motion.div>
            )
          })}
        </section>

        {/* Tier info */}
        <div className="text-xs font-mono-dm opacity-20 pb-8">
          {project.tier === 'paid' ? '✦ 付费版' : '◇ 免费版'} · {project.budget_used} 个来源
        </div>
      </main>
      <MobileNav />
    </div>
  )
}
