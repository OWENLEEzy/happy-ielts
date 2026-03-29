'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
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
        stroke="rgba(109,40,217,0.12)"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--primary)"
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
        fontFamily="Plus Jakarta Sans, sans-serif"
        fontWeight={700}
        fill="var(--primary)"
      >
        {Math.round(value * 100)}%
      </text>
    </svg>
  )
}

function TrendBadge({ trend }: { trend: DimensionState['trend'] }) {
  if (trend === 'improving')
    return <span className="text-xs font-bold font-label text-primary">↑ 进步中</span>
  if (trend === 'worsening')
    return <span className="text-xs font-bold font-label text-error">↓ 需加强</span>
  return <span className="text-xs font-label text-on-surface-variant">— 稳定</span>
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
      <div className="min-h-screen flex items-center justify-center bg-background">
        <motion.div
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.6, repeat: Infinity }}
          className="flex gap-1.5"
        >
          {[0, 1, 2].map((i) => (
            <span key={i} className="w-2.5 h-2.5 bg-primary rounded-full inline-block" />
          ))}
        </motion.div>
      </div>
    )
  }

  const worseningChapters = project.chapters
    .map((ch) => {
      const dim = project.dimensions[ch.title]
      return dim && dim.trend === 'worsening' && dim.mastery < 0.5 ? ch.title : null
    })
    .filter((t): t is string => t !== null)

  return (
    <div className="min-h-screen bg-background">
      <Header />

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-12">
        {/* Goal progress hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-end gap-8"
        >
          <div>
            <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label mb-2">
              学习目标
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold font-headline text-on-surface leading-tight">
              {project.goal_outcome}
            </h1>

            {fsrsDueCount > 0 && (
              <motion.button
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                onClick={() => router.push(`/learn/${projectId}/review`)}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold font-label bg-primary/10 text-primary border border-primary/20 hover:bg-primary/15 transition-colors"
              >
                ⟳ 开始复习
                <span className="px-1.5 py-0.5 rounded-full text-xs bg-primary text-white">
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
              className="flex items-start gap-3 rounded-xl px-4 py-3 bg-error/5 border border-error/10"
            >
              <span className="flex-1 text-sm font-body text-error">
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
                className="text-xs text-error/50 hover:text-error/80 transition-colors flex-shrink-0 mt-0.5"
                aria-label="关闭提示"
              >
                ✕
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Chapters + lessons */}
        <section className="space-y-8">
          <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
            课程地图
          </div>

          {project.chapters.map((ch, ci) => {
            const dim: DimensionState | undefined = project.dimensions[ch.title]

            return (
              <motion.div
                key={ch.title}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + ci * 0.08 }}
              >
                {/* Chapter header */}
                <div className="flex items-center gap-3 mb-3">
                  <div className="text-[11px] font-black text-on-surface-variant uppercase tracking-widest font-label">
                    Chapter {ci + 1} · {ch.title}
                  </div>

                  {dim && (
                    <>
                      <MasteryRing value={dim.mastery} size={28} />
                      <TrendBadge trend={dim.trend} />
                      <span className="text-xs text-on-surface-variant/40 font-label">
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
                            className={`w-full text-left rounded-xl px-5 py-4 flex items-center gap-4 transition-all border ${
                              isNew
                                ? 'bg-primary-container/30 border-primary/20 shadow-[0_0_16px_color-mix(in_srgb,var(--primary)_10%,transparent)]'
                                : isReady
                                  ? 'bg-surface-container-lowest border-outline-variant/20 hover:shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)]'
                                  : 'bg-surface-container border-transparent cursor-not-allowed opacity-50'
                            }`}
                          >
                            {/* Status dot */}
                            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                              isNew ? 'bg-primary' : isReady ? 'bg-primary/50' : 'bg-outline-variant/30'
                            }`} />

                            {/* Title */}
                            <span className={`flex-1 text-sm font-body ${
                              isReady ? 'text-on-surface font-medium' : 'text-on-surface-variant'
                            }`}>
                              {lesson.title}
                            </span>

                            {/* Newly unlocked badge */}
                            {isNew && (
                              <motion.span
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={{ type: 'spring', stiffness: 300, delay: 0.3 }}
                                className="text-xs font-bold font-label px-2.5 py-1 rounded-full bg-primary/10 text-primary"
                              >
                                新解锁
                              </motion.span>
                            )}

                            {/* Arrow */}
                            {isReady && !isNew && (
                              <span className="text-xs text-on-surface-variant opacity-0 group-hover:opacity-60 transition-opacity">
                                →
                              </span>
                            )}

                            {/* Pending */}
                            {!isReady && (
                              <span className="text-xs font-label text-on-surface-variant/40">
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
        <div className="text-xs text-on-surface-variant/30 font-label pb-8">
          {project.tier === 'paid' ? '✦ 付费版' : '◇ 免费版'} · {project.budget_used} 个来源
        </div>
      </main>
      <MobileNav />
    </div>
  )
}
