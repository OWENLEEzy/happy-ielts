'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { client } from '@/lib/client'
import type { components } from '@/types/api'
import { DogAvatar } from '@/components/DogAvatar'

type Project = components['schemas']['GeneralProject']

export default function HomePage() {
  const router = useRouter()
  const [englishOnboarded, setEnglishOnboarded] = useState<boolean | null>(null)
  const [englishReady, setEnglishReady] = useState<boolean | null>(null)
  const [activeProject, setActiveProject] = useState<Project | null>(null)

  useEffect(() => {
    client
      .GET('/api/onboarding/status')
      .then(({ data }) => {
        setEnglishOnboarded(data?.ready ?? false)
        if (data?.ready) {
          client
            .GET('/api/planner/status')
            .then(({ data: p }) => setEnglishReady(p?.ready ?? false))
            .catch(() => setEnglishReady(false))
        } else {
          setEnglishReady(false)
        }
      })
      .catch(() => {
        setEnglishOnboarded(false)
        setEnglishReady(false)
      })

    client
      .GET('/api/learn/projects', {})
      .then(({ data }) => {
        const active = (data ?? []).find((p) => p.status === 'active') ?? null
        setActiveProject(active)
      })
      .catch(() => {})
  }, [])

  const enterEnglish = async () => {
    localStorage.setItem('appMode', 'english')
    if (!englishOnboarded) {
      router.push('/onboarding')
      return
    }
    router.push('/lesson')
  }

  const enterGeneral = () => {
    localStorage.setItem('appMode', 'general')
    router.push('/learn')
  }

  const englishBadge =
    englishReady === null
      ? null
      : !englishOnboarded
        ? { label: '未初始化', cls: 'bg-surface-container text-on-surface-variant' }
        : englishReady
          ? { label: '● 就绪', cls: 'bg-primary/10 text-primary' }
          : { label: '○ 备课中', cls: 'bg-surface-container text-on-surface-variant' }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-10 px-6">
      {/* Logo + title */}
      <div className="flex flex-col items-center gap-3">
        <DogAvatar
          role="relationship"
          size={80}
          emphasis="hero"
          alt="Happy Learning 品牌大使"
        />
        <h1 className="text-3xl font-extrabold font-headline text-on-surface tracking-tight">
          Happy Learning
        </h1>
        <p className="text-sm text-on-surface-variant font-body">选择今日学习内容</p>
      </div>

      {/* Mode cards */}
      <div className="flex flex-col gap-4 w-full max-w-sm">
        {/* English */}
        <button
          onClick={enterEnglish}
          className="w-full bg-surface-container-lowest rounded-xl p-6 text-left shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)] hover:shadow-[0_4px_20px_color-mix(in_srgb,var(--primary)_10%,transparent)] transition-shadow group"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-base font-bold font-label text-on-surface">英语飞轮</span>
            {englishBadge && (
              <span
                className={`text-xs font-bold font-label px-2 py-0.5 rounded-full ${englishBadge.cls}`}
              >
                {englishBadge.label}
              </span>
            )}
          </div>
          <p className="text-xs text-on-surface-variant font-body">
            每日文章精读 · 写作训练 · 生词复习
          </p>
          <div className="mt-4 flex justify-end">
            <span className="signature-gradient text-white text-xs font-bold font-label px-4 py-1.5 rounded-full shadow shadow-primary/25 group-hover:scale-105 transition-transform inline-block">
              进入 →
            </span>
          </div>
        </button>

        {/* General learning */}
        <button
          onClick={enterGeneral}
          className="w-full bg-surface-container-lowest rounded-xl p-6 text-left shadow-[0_2px_12px_color-mix(in_srgb,var(--primary)_6%,transparent)] hover:shadow-[0_4px_20px_color-mix(in_srgb,var(--primary)_10%,transparent)] transition-shadow group"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-base font-bold font-label text-on-surface">通用技能学习</span>
            {activeProject && (
              <span className="text-xs font-bold font-label px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                ● 进行中
              </span>
            )}
          </div>
          <p className="text-xs text-on-surface-variant font-body">
            {activeProject
              ? `继续：${activeProject.user_topic}`
              : 'AI 备课 · 吉他 / 投资 / 摄影 / 任何你想学的'}
          </p>
          <div className="mt-4 flex justify-end">
            <span className="signature-gradient text-white text-xs font-bold font-label px-4 py-1.5 rounded-full shadow shadow-primary/25 group-hover:scale-105 transition-transform inline-block">
              进入 →
            </span>
          </div>
        </button>
      </div>
    </div>
  )
}
