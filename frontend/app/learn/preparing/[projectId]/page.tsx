'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL } from '@/lib/learn-theme'
import { client } from '@/lib/client'
import type { components } from '@/types/api'

type GeneralProject = components['schemas']['GeneralProject']
type ProjectStatus = GeneralProject['status']

const PHASES: { key: ProjectStatus; label: string; detail: (p: GeneralProject) => string }[] = [
  { key: 'onboarding', label: '了解你的学习目标', detail: () => '访谈完成' },
  { key: 'researching', label: '深度研究中', detail: (p) => `已发现 ${p.budget_used} 个来源` },
  { key: 'extracting', label: '提取知识、生成课程', detail: () => '构建专属学习地图' },
  { key: 'active', label: '第一节课已就绪', detail: () => '可以开始学习了' },
]

const STATUS_ORDER: ProjectStatus[] = ['onboarding', 'researching', 'extracting', 'active']

// Constellation node positions (relative %)
const NODES = Array.from({ length: 32 }, (_, i) => ({
  id: i,
  x: 10 + Math.sin(i * 1.7) * 38 + (i % 7) * 11,
  y: 10 + Math.cos(i * 1.3) * 35 + Math.floor(i / 7) * 22,
}))

const EDGES = NODES.slice(0, 24).map((n, i) => ({
  from: n.id,
  to: NODES[(i + 3 + (i % 5)) % NODES.length].id,
}))

export default function PreparingPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const router = useRouter()
  const [project, setProject] = useState<GeneralProject | null>(null)
  const [litNodes, setLitNodes] = useState<Set<number>>(new Set())
  const [unlocked, setUnlocked] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const nodeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Animate nodes lighting up
  useEffect(() => {
    let count = 0
    nodeIntervalRef.current = setInterval(() => {
      count++
      setLitNodes((prev) => {
        const next = new Set(prev)
        const idx = Math.floor(Math.random() * NODES.length)
        next.add(idx)
        return next
      })
      if (count > 40) clearInterval(nodeIntervalRef.current!)
    }, 300)
    return () => clearInterval(nodeIntervalRef.current!)
  }, [])

  // Poll project status
  useEffect(() => {
    const fetchProject = async () => {
      try {
        const { data, response } = await client.GET('/api/learn/projects/{project_id}', {
          params: { path: { project_id: Number(projectId) } },
        })
        if (!response.ok) return
        if (!data) return
        setProject(data)
        if (data.status === 'active' && !unlocked) {
          setUnlocked(true)
          setTimeout(() => router.push(`/learn/${projectId}`), 2800)
        }
      } catch {
        /* ignore */
      }
    }

    fetchProject()
    intervalRef.current = setInterval(fetchProject, 5000)
    return () => clearInterval(intervalRef.current!)
  }, [projectId, router, unlocked])

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: GL.bg,
        color: GL.fg,
      }}
    >
      <Header dark />

      <main className="flex-1 flex flex-col lg:flex-row items-center justify-center gap-12 px-6 py-8 max-w-5xl mx-auto w-full">
        {/* Left: constellation visualization */}
        <div className="relative w-72 h-72 flex-shrink-0">
          {/* Ambient glow */}
          <div
            className="absolute inset-0 rounded-full"
            style={{
              background: 'radial-gradient(circle, rgba(201,168,76,0.07) 0%, transparent 70%)',
              filter: 'blur(20px)',
            }}
          />

          <svg className="w-full h-full" viewBox="0 0 100 100">
            {/* Edges */}
            {EDGES.map((e) => {
              const from = NODES[e.from]
              const to = NODES[e.to]
              const isLit = litNodes.has(e.from) && litNodes.has(e.to)
              return (
                <line
                  key={`${e.from}-${e.to}`}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={isLit ? '#c9a84c' : 'rgba(201,168,76,0.08)'}
                  strokeWidth={isLit ? 0.4 : 0.2}
                  style={{ transition: 'stroke 0.8s ease, stroke-width 0.8s ease' }}
                />
              )
            })}
            {/* Nodes */}
            {NODES.map((n) => {
              const isLit = litNodes.has(n.id)
              return (
                <circle
                  key={n.id}
                  cx={n.x}
                  cy={n.y}
                  r={isLit ? 1.2 : 0.6}
                  fill={isLit ? '#c9a84c' : 'rgba(201,168,76,0.25)'}
                  style={{ transition: 'all 0.6s ease' }}
                />
              )
            })}
          </svg>

          {/* Center pulse */}
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div
              animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
              className="w-8 h-8 rounded-full border"
              style={{ borderColor: 'rgba(201,168,76,0.5)', background: 'rgba(201,168,76,0.08)' }}
            />
          </div>
        </div>

        {/* Right: status + phases */}
        <div className="flex flex-col gap-8 max-w-sm w-full">
          <div>
            <h1
              className="font-cormorant font-light leading-tight"
              style={{ fontSize: '2.6rem', color: GL.fg }}
            >
              老师正在
              <br />
              <em style={{ color: GL.amber }}>备课中</em>
            </h1>
            <p className="mt-2 text-sm opacity-50" style={{ fontFamily: 'Manrope, sans-serif' }}>
              为你定制专属学习路径，通常需要 15–30 分钟
            </p>
          </div>

          {/* Phase timeline */}
          <div className="space-y-4">
            {PHASES.map((phase, idx) => {
              const isDone = project ? STATUS_ORDER.indexOf(project.status) > idx : false
              const isActive = project ? STATUS_ORDER.indexOf(project.status) === idx : idx === 0
              const isPending = !isDone && !isActive

              return (
                <motion.div
                  key={phase.key}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: isPending ? 0.3 : 1, x: 0 }}
                  transition={{ delay: idx * 0.12, duration: 0.5 }}
                  className="flex items-start gap-4"
                >
                  {/* Icon */}
                  <div
                    className="mt-0.5 w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs border transition-all duration-700"
                    style={{
                      borderColor: isDone
                        ? '#c9a84c'
                        : isActive
                          ? 'rgba(201,168,76,0.6)'
                          : 'rgba(240,235,224,0.15)',
                      background: isDone
                        ? '#c9a84c'
                        : isActive
                          ? 'rgba(201,168,76,0.1)'
                          : 'transparent',
                      color: isDone ? '#0f0d1a' : isActive ? '#c9a84c' : 'rgba(240,235,224,0.3)',
                    }}
                  >
                    {isDone ? (
                      '✓'
                    ) : isActive ? (
                      <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                        className="w-3 h-3 rounded-full border-t border-r"
                        style={{ borderColor: '#c9a84c' }}
                      />
                    ) : (
                      '○'
                    )}
                  </div>

                  {/* Label */}
                  <div>
                    <div
                      className="text-sm font-medium"
                      style={{
                        fontFamily: 'Manrope, sans-serif',
                        color: isDone ? '#f0ebe0' : isActive ? '#f0ebe0' : 'rgba(240,235,224,0.3)',
                      }}
                    >
                      {phase.label}
                    </div>
                    {(isDone || isActive) && project && (
                      <div
                        className="text-xs mt-0.5 font-mono-dm"
                        style={{ color: '#c9a84c', opacity: 0.7 }}
                      >
                        {phase.detail(project)}
                      </div>
                    )}
                  </div>
                </motion.div>
              )
            })}
          </div>

          {/* Leave note */}
          <p className="text-xs opacity-25 font-mono-dm leading-relaxed">
            可以关闭此页面，完成后通知你返回开始学习
          </p>
        </div>
      </main>

      {/* Unlock overlay */}
      <AnimatePresence>
        {unlocked && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="fixed inset-0 flex items-center justify-center z-50"
            style={{ background: 'rgba(15,13,26,0.92)', backdropFilter: 'blur(12px)' }}
          >
            <div className="text-center space-y-6">
              {/* Expanding golden ring */}
              <div className="relative w-32 h-32 mx-auto">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="absolute inset-0 rounded-full border"
                    style={{ borderColor: 'rgba(201,168,76,0.4)' }}
                    initial={{ scale: 0.5, opacity: 1 }}
                    animate={{ scale: 2.5, opacity: 0 }}
                    transition={{
                      duration: 1.8,
                      delay: i * 0.5,
                      repeat: Infinity,
                      ease: 'easeOut',
                    }}
                  />
                ))}
                <motion.div
                  className="absolute inset-0 rounded-full flex items-center justify-center text-4xl"
                  style={{
                    background: 'rgba(201,168,76,0.12)',
                    border: '1px solid rgba(201,168,76,0.4)',
                  }}
                  initial={{ scale: 0, rotate: -20 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.2 }}
                >
                  ✦
                </motion.div>
              </div>

              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
              >
                <h2 className="font-cormorant font-light text-4xl" style={{ color: GL.amber }}>
                  第一节课已解锁
                </h2>
                <p
                  className="mt-2 text-sm opacity-50"
                  style={{ fontFamily: 'Manrope, sans-serif' }}
                >
                  即将跳转...
                </p>
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <MobileNav />
    </div>
  )
}
