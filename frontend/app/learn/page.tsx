'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { client } from '@/lib/client'
import type { components } from '@/types/api'

type Project = components['schemas']['GeneralProject']

const STATUS_LABEL: Record<string, string> = {
  onboarding: '备课中',
  researching: '研究中',
  active: '进行中',
  completed: '已完成',
}

export default function LearnLandingPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client
      .GET('/api/learn/projects')
      .then(({ data }) => setProjects(data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const activeProjects = projects.filter((p) => p.status === 'active')
  const otherProjects = projects.filter((p) => p.status !== 'active')

  const handleProjectClick = (p: Project) => {
    if (p.status === 'active') {
      router.push(`/learn/${p.id}`)
    } else if (p.status === 'onboarding') {
      router.push(`/learn/onboarding`)
    } else if (p.status === 'researching') {
      router.push(`/learn/preparing/${p.id}`)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Header />

      <main className="flex-1 max-w-4xl mx-auto w-full px-6 py-12 space-y-12">
        {/* Existing projects */}
        {(loading || projects.length > 0) && (
          <motion.section
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="space-y-4"
          >
            <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
              我的学习项目
            </div>

            {loading ? (
              <div className="space-y-3">
                {[0, 1].map((i) => (
                  <div
                    key={i}
                    className="h-16 rounded-xl bg-surface-container-low animate-pulse"
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {[...activeProjects, ...otherProjects].map((p, i) => (
                  <motion.button
                    key={p.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    onClick={() => handleProjectClick(p)}
                    className="w-full text-left rounded-xl px-5 py-4 flex items-center gap-4 bg-surface-container-lowest shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)] hover:shadow-[0_4px_16px_color-mix(in_srgb,var(--primary)_10%,transparent)] transition-shadow group"
                  >
                    {/* Status dot */}
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      p.status === 'active' ? 'bg-primary' : 'bg-outline-variant'
                    }`} />

                    {/* Topic */}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold font-body text-on-surface truncate">
                        {p.user_topic}
                      </div>
                      {p.goal_profile?.goal_outcome && (
                        <div className="text-xs text-on-surface-variant font-body truncate mt-0.5">
                          {p.goal_profile.goal_outcome}
                        </div>
                      )}
                    </div>

                    {/* Status badge */}
                    <span className={`text-xs font-bold font-label flex-shrink-0 ${
                      p.status === 'active' ? 'text-primary' : 'text-on-surface-variant'
                    }`}>
                      {STATUS_LABEL[p.status] ?? p.status}
                    </span>

                    {/* Arrow */}
                    <span className="text-xs text-on-surface-variant opacity-0 group-hover:opacity-60 transition-opacity flex-shrink-0">
                      →
                    </span>
                  </motion.button>
                ))}
              </div>
            )}
          </motion.section>
        )}

        {/* New project CTA */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="space-y-6"
        >
          {projects.length > 0 && (
            <div className="text-[11px] font-black text-primary uppercase tracking-widest font-label">
              开启新项目
            </div>
          )}

          <div className={projects.length === 0 ? 'text-center space-y-6' : 'space-y-4'}>
            {projects.length === 0 && (
              <>
                <h1 className="text-4xl md:text-5xl font-extrabold font-headline text-on-surface leading-tight">
                  掌握任何<br />
                  <span className="text-primary">你想学的</span>
                </h1>
                <p className="max-w-md mx-auto text-base leading-relaxed text-on-surface-variant font-body">
                  告诉我你的目标，AI 老师为你深度备课，生成专属学习地图，一节一节带你抵达。
                </p>
              </>
            )}

            <div className={projects.length === 0 ? 'flex justify-center' : ''}>
              <button
                onClick={() => router.push('/learn/onboarding')}
                className="signature-gradient text-white px-7 py-3 rounded-full font-bold text-sm font-label shadow-lg shadow-primary/25 hover:scale-105 transition-transform inline-flex items-center gap-2"
              >
                {projects.length === 0 ? '开始学习' : '+ 新建项目'}
                <span>→</span>
              </button>
            </div>
          </div>

          <p className="text-xs text-on-surface-variant/40 font-body">
            想练英语？
            <Link href="/lesson" className="underline hover:opacity-60 transition-opacity ml-1">
              切换到英语飞轮
            </Link>
          </p>
        </motion.section>
      </main>

      <MobileNav />
    </div>
  )
}
