'use client'
import { useEffect, useSyncExternalStore } from 'react'
import { useRouter } from 'next/navigation'
import { client } from '@/lib/client'

type AppMode = 'english' | 'general'

function subscribeToStorage(cb: () => void) {
  window.addEventListener('storage', cb)
  return () => window.removeEventListener('storage', cb)
}

export default function HomePage() {
  const router = useRouter()
  const mode = useSyncExternalStore(
    subscribeToStorage,
    () => localStorage.getItem('appMode') as AppMode | null,
    () => null,
  )

  const chooseMode = (m: AppMode) => {
    localStorage.setItem('appMode', m)
    redirectForMode(m, router)
  }

  useEffect(() => {
    if (mode) redirectForMode(mode, router)
  }, [mode, router])

  if (mode) return null
  return <ModeSelectScreen onChoose={chooseMode} />
}

async function redirectForMode(mode: AppMode, router: ReturnType<typeof useRouter>) {
  if (mode === 'english') {
    const [onb, planner] = await Promise.all([
      client
        .GET('/api/onboarding/status')
        .then(({ data }) => (data as { ready: boolean } | undefined) ?? { ready: false })
        .catch(() => ({ ready: false })),
      client
        .GET('/api/planner/status')
        .then(({ data }) => (data as { ready: boolean } | undefined) ?? { ready: false })
        .catch(() => ({ ready: false })),
    ])
    if (!onb.ready) {
      router.replace('/onboarding')
      return
    }
    if (!planner.ready) {
      router.replace('/lesson?loading=true')
      return
    }
    router.replace('/lesson')
  } else {
    const projectId = localStorage.getItem('generalProjectId')
    if (!projectId) {
      router.replace('/learn/onboarding')
      return
    }
    router.replace(`/learn/${projectId}`)
  }
}

function ModeSelectScreen({ onChoose }: { onChoose: (m: AppMode) => void }) {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-8 px-6"
      style={{ background: 'linear-gradient(160deg, #0f0d1a 0%, #1a1428 50%, #0d1118 100%)' }}
    >
      <div className="text-center space-y-2">
        <h1 className="font-cormorant font-light text-5xl" style={{ color: '#f0ebe0' }}>
          Happy Learning
        </h1>
        <p
          className="text-sm opacity-40"
          style={{ color: '#f0ebe0', fontFamily: 'Manrope, sans-serif' }}
        >
          选择你的学习模式
        </p>
      </div>
      <div className="flex flex-col gap-4 w-full max-w-sm">
        <button
          onClick={() => onChoose('english')}
          className="w-full p-6 rounded-2xl border text-left transition-all hover:scale-[1.02]"
          style={{ background: 'rgba(109,40,217,0.08)', borderColor: 'rgba(109,40,217,0.3)' }}
        >
          <div className="text-base font-semibold mb-1" style={{ color: '#a78bfa' }}>
            英语飞轮
          </div>
          <div
            className="text-xs opacity-50"
            style={{ color: '#f0ebe0', fontFamily: 'Manrope, sans-serif' }}
          >
            每日文章精读 + 写作训练 + 生词复习
          </div>
        </button>
        <button
          onClick={() => onChoose('general')}
          className="w-full p-6 rounded-2xl border text-left transition-all hover:scale-[1.02]"
          style={{ background: 'rgba(201,168,76,0.08)', borderColor: 'rgba(201,168,76,0.3)' }}
        >
          <div className="text-base font-semibold mb-1" style={{ color: '#c9a84c' }}>
            通用技能学习
          </div>
          <div
            className="text-xs opacity-50"
            style={{ color: '#f0ebe0', fontFamily: 'Manrope, sans-serif' }}
          >
            AI 备课 · 吉他 / 投资 / 摄影 / 任何你想学的
          </div>
        </button>
      </div>
    </div>
  )
}
