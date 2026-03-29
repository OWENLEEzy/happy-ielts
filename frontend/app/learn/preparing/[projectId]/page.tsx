'use client'
import { useEffect, useState, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { client } from '@/lib/client'
import { getRandomTeacherDogUrl } from '@/lib/constants'
import Image from 'next/image'
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

export default function PreparingPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const router = useRouter()
  const [project, setProject] = useState<GeneralProject | null>(null)
  const [unlocked, setUnlocked] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [dogUrl] = useState(getRandomTeacherDogUrl)

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
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-surface-container-lowest rounded-xl p-10 text-center shadow-[0_4px_24px_color-mix(in_srgb,var(--primary)_8%,transparent)]">

          {/* Professor 金毛 */}
          <div className="relative w-20 h-20 rounded-full overflow-hidden border-4 border-primary/20 shadow-xl mx-auto mb-6">
            {dogUrl && <Image src={dogUrl} fill sizes="80px" className="object-cover" alt="Professor 金毛" />}
          </div>

          <h2 className="text-xl font-extrabold font-headline text-primary mb-2">
            AI 正在为你备课
          </h2>
          <p className="text-sm text-on-surface-variant font-body mb-8">
            {project ? `正在研究：${project.user_topic}` : '正在准备...'}
          </p>

          {/* Phase timeline */}
          <div className="flex flex-col gap-3 text-left mb-8">
            {PHASES.map((phase, idx) => {
              const currentIdx = project ? STATUS_ORDER.indexOf(project.status) : 0
              const isDone = currentIdx > idx
              const isActive = currentIdx === idx
              const isPending = !isDone && !isActive

              return (
                <motion.div
                  key={phase.key}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: isPending ? 0.35 : 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className="flex items-center gap-3"
                >
                  <span className={`w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold font-label transition-colors ${
                    isDone
                      ? 'bg-primary/15 text-primary'
                      : isActive
                        ? 'bg-primary text-white'
                        : 'bg-outline-variant/20 text-on-surface-variant/40'
                  }`}>
                    {isDone ? '✓' : idx + 1}
                  </span>
                  <div className="flex-1">
                    <div className={`text-sm font-body ${isDone || isActive ? 'text-on-surface' : 'text-on-surface-variant/40'}`}>
                      {phase.label}
                    </div>
                    {(isDone || isActive) && project && (
                      <div className="text-xs text-primary/70 font-label">{phase.detail(project)}</div>
                    )}
                  </div>
                  {isActive && (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                      className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent flex-shrink-0"
                    />
                  )}
                </motion.div>
              )
            })}
          </div>

          {/* Leave note */}
          <p className="text-xs text-on-surface-variant/40 font-body leading-relaxed">
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
            className="fixed inset-0 flex items-center justify-center z-50 bg-background/90 backdrop-blur-md"
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.1 }}
              className="text-center space-y-6"
            >
              <div className="w-24 h-24 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-4xl mx-auto shadow-[0_0_40px_color-mix(in_srgb,var(--primary)_20%,transparent)]">
                ✓
              </div>
              <div>
                <h2 className="text-3xl font-extrabold font-headline text-primary mb-2">
                  第一节课已解锁
                </h2>
                <p className="text-sm text-on-surface-variant font-body">即将跳转...</p>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <MobileNav />
    </div>
  )
}
