'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'

interface Lesson {
  id: number
  chapter: number
  lesson: number
  title: string
  status: 'pending' | 'ready'
}

interface Chapter {
  title: string
  lessons: Lesson[]
}

interface StudentDimension {
  mastery: number
  sessions: number
  trend: 'improving' | 'stable' | 'worsening'
}

interface Project {
  id: number
  user_topic: string
  goal_outcome: string
  goal_progress: number
  dimensions: Record<string, StudentDimension>
  chapters: Chapter[]
  tier: 'free' | 'paid'
  budget_used: number
}

function MasteryRing({ value, size = 48 }: { value: number; size?: number }) {
  const r = (size - 8) / 2
  const circ = 2 * Math.PI * r
  const dash = circ * value
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(201,168,76,0.12)" strokeWidth={3} />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#c9a84c" strokeWidth={3}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 1s ease' }}
      />
      <text
        x={size / 2} y={size / 2 + 5}
        textAnchor="middle"
        fontSize={size < 40 ? 9 : 11}
        fontFamily="DM Mono, monospace"
        fill="#c9a84c"
      >
        {Math.round(value * 100)}%
      </text>
    </svg>
  )
}

export default function ProjectDashboard() {
  const { projectId } = useParams<{ projectId: string }>()
  const router = useRouter()
  const [project, setProject] = useState<Project | null>(null)
  const [newlyUnlocked, setNewlyUnlocked] = useState<number | null>(null)

  useEffect(() => {
    fetch(`/api/learn/projects/${projectId}/dashboard`)
      .then((r) => r.json())
      .then((data: Project) => {
        setProject(data)
        // Find first ready lesson to highlight
        for (const ch of data.chapters) {
          const first = ch.lessons.find((l) => l.status === 'ready')
          if (first) { setNewlyUnlocked(first.id); break }
        }
      })
      .catch(() => {})
  }, [projectId])

  if (!project) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#0f0d1a', color: '#f0ebe0' }}>
        <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.6, repeat: Infinity }}>
          <span className="font-mono-dm text-sm opacity-40">载入中...</span>
        </motion.div>
      </div>
    )
  }

  const allDimensions = Object.entries(project.dimensions)

  return (
    <div className="min-h-screen" style={{
      background: 'linear-gradient(160deg, #0f0d1a 0%, #1a1428 60%, #0d1118 100%)',
      color: '#f0ebe0',
    }}>
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5 max-w-5xl mx-auto border-b" style={{ borderColor: 'rgba(240,235,224,0.06)' }}>
        <Link href="/learn" className="text-xs font-mono-dm tracking-widest uppercase opacity-30 hover:opacity-70 transition-opacity">
          ← 学习中心
        </Link>
        <span className="text-xs font-mono-dm opacity-20">{project.user_topic}</span>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-12">

        {/* Goal progress hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-end gap-8"
        >
          <div>
            <div className="text-xs font-mono-dm tracking-widest uppercase mb-2" style={{ color: 'rgba(201,168,76,0.6)' }}>
              学习目标
            </div>
            <h1 className="font-cormorant font-light leading-tight" style={{ fontSize: 'clamp(1.8rem, 4vw, 3rem)' }}>
              {project.goal_outcome}
            </h1>
          </div>
          <div className="flex-shrink-0 ml-auto">
            <MasteryRing value={project.goal_progress} size={80} />
          </div>
        </motion.div>

        {/* Dimension grid */}
        {allDimensions.length > 0 && (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="text-xs font-mono-dm tracking-widest uppercase mb-4" style={{ color: 'rgba(201,168,76,0.5)' }}>
              掌握进度
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {allDimensions.map(([name, dim]) => (
                <div key={name} className="rounded-xl p-4 flex items-center gap-3 border" style={{
                  background: 'rgba(201,168,76,0.03)',
                  borderColor: 'rgba(201,168,76,0.1)',
                }}>
                  <MasteryRing value={dim.mastery} size={40} />
                  <div className="min-w-0">
                    <div className="text-sm truncate" style={{ fontFamily: 'Manrope, sans-serif', fontWeight: 500 }}>{name}</div>
                    <div className="text-xs mt-0.5 font-mono-dm" style={{
                      color: dim.trend === 'improving' ? '#6fba8a' : dim.trend === 'worsening' ? '#ba6f6f' : 'rgba(240,235,224,0.3)',
                    }}>
                      {dim.trend === 'improving' ? '↑ 进步中' : dim.trend === 'worsening' ? '↓ 需加强' : '— 稳定'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.section>
        )}

        {/* Chapters + lessons */}
        <section className="space-y-8">
          <h2 className="text-xs font-mono-dm tracking-widest uppercase" style={{ color: 'rgba(201,168,76,0.5)' }}>
            课程地图
          </h2>

          {project.chapters.map((ch, ci) => (
            <motion.div
              key={ci}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + ci * 0.08 }}
            >
              <div className="text-xs font-mono-dm tracking-widest uppercase mb-3" style={{ color: 'rgba(240,235,224,0.35)' }}>
                Chapter {ci + 1} · {ch.title}
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
                        transition={isNew ? { type: 'spring', stiffness: 180, damping: 16 } : undefined}
                      >
                        <button
                          disabled={!isReady}
                          onClick={() => isReady && router.push(`/learn/${projectId}/lesson/${lesson.id}`)}
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
                          <div className="w-2 h-2 rounded-full flex-shrink-0 transition-all duration-500" style={{
                            background: isNew
                              ? '#c9a84c'
                              : isReady
                              ? 'rgba(201,168,76,0.5)'
                              : 'rgba(240,235,224,0.12)',
                            boxShadow: isNew ? '0 0 8px #c9a84c' : 'none',
                          }} />

                          {/* Title */}
                          <span className="flex-1 text-sm" style={{
                            fontFamily: 'Manrope, sans-serif',
                            fontWeight: isReady ? 500 : 400,
                            color: isReady ? '#f0ebe0' : 'rgba(240,235,224,0.3)',
                          }}>
                            {lesson.title}
                          </span>

                          {/* Newly unlocked badge */}
                          {isNew && (
                            <motion.span
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ type: 'spring', stiffness: 300, delay: 0.3 }}
                              className="text-xs px-2.5 py-1 rounded-full font-mono-dm"
                              style={{ background: 'rgba(201,168,76,0.2)', color: '#c9a84c' }}
                            >
                              新解锁
                            </motion.span>
                          )}

                          {/* Arrow */}
                          {isReady && !isNew && (
                            <span className="text-xs opacity-0 group-hover:opacity-40 transition-opacity font-mono-dm">→</span>
                          )}

                          {/* Pending lock */}
                          {!isReady && (
                            <span className="text-xs font-mono-dm" style={{ color: 'rgba(240,235,224,0.15)' }}>准备中</span>
                          )}
                        </button>
                      </motion.div>
                    </AnimatePresence>
                  )
                })}
              </div>
            </motion.div>
          ))}
        </section>

        {/* Tier info */}
        <div className="text-xs font-mono-dm opacity-20 pb-8">
          {project.tier === 'paid' ? '✦ 付费版' : '◇ 免费版'} · {project.budget_used} 个来源
        </div>
      </main>
    </div>
  )
}
