'use client'
import { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { getRandomTogetherDogUrl, getRandomUserDogUrl } from '@/lib/constants'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { GL } from '@/lib/learn-theme'

export function Header({ streak = 0, dark }: { streak?: number; dark?: boolean }) {
  const pathname = usePathname()
  const router = useRouter()
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [mode, setMode] = useState<string | null>(null)

  useEffect(() => {
    setLogoUrl(getRandomTogetherDogUrl())
    setAvatarUrl(getRandomUserDogUrl())
    setMode(localStorage.getItem('appMode'))
  }, [])

  const switchMode = () => {
    localStorage.removeItem('appMode')
    router.push('/')
  }

  const headerBg = dark ? '' : 'bg-background/90 backdrop-blur-md border-outline-variant/20'

  return (
    <header
      className={`sticky top-0 z-50 h-16 ${headerBg} border-b flex items-center`}
      style={
        dark
          ? { background: GL.headerBg, borderColor: GL.headerBorder, backdropFilter: 'blur(12px)' }
          : undefined
      }
    >
      <div className="flex items-center justify-between max-w-5xl mx-auto px-6 gap-4 w-full">
        {/* Logo */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="relative w-9 h-9 rounded-full overflow-hidden border-2 border-primary/30 flex-shrink-0">
            {logoUrl && (
              <Image src={logoUrl} fill sizes="36px" className="object-cover" alt="logo" />
            )}
          </div>
          <span
            className={`text-lg font-black tracking-tighter font-headline hidden sm:block ${dark ? 'text-amber-300/80' : 'text-primary'}`}
          >
            Happy Learning
          </span>
        </div>

        {/* Nav links (desktop) — English mode only */}
        {mode === 'english' && (
          <nav className="hidden md:flex items-center gap-1">
            {[{ href: '/lesson', label: '今日课程' }].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`px-4 py-1.5 rounded-full text-sm font-bold font-label transition-colors ${
                  pathname === href
                    ? 'bg-primary/10 text-primary'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        )}

        {/* Right */}
        <div className="flex items-center gap-3 ml-auto">
          {streak > 0 && (
            <div className="hidden sm:flex items-center gap-1.5 bg-error/10 px-3 py-1.5 rounded-full text-sm font-bold text-error font-label">
              <span
                className="material-symbols-outlined text-[17px]"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                local_fire_department
              </span>
              {streak}天
            </div>
          )}

          {/* Avatar → Sheet */}
          <Sheet>
            <SheetTrigger className="relative w-9 h-9 rounded-full overflow-hidden border-2 border-primary/20 flex-shrink-0 hover:border-primary/60 transition-colors">
              {avatarUrl && (
                <Image src={avatarUrl} fill sizes="36px" className="object-cover" alt="我的设置" />
              )}
            </SheetTrigger>
            <SheetContent side="right" className="w-72 p-6">
              <div className="flex flex-col gap-6 pt-4">
                <div className="font-semibold text-sm text-on-surface">个人设置</div>

                {mode === 'english' && <EnglishSettings />}

                {mode === 'general' && (
                  <div
                    className="text-xs opacity-50 text-on-surface"
                    style={{ fontFamily: 'Manrope, sans-serif' }}
                  >
                    通用技能学习模式
                  </div>
                )}

                <div className="border-t pt-4">
                  <button
                    onClick={switchMode}
                    className="text-xs text-error opacity-60 hover:opacity-100 transition-opacity"
                  >
                    切换学习模式
                  </button>
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  )
}

function EnglishSettings() {
  const [bandwidth, setBandwidth] = useState<number | null>(null)
  const [writingMode, setWritingMode] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/profile')
      .then((r) => r.json())
      .then((d) => {
        setBandwidth(d.bandwidth_minutes ?? null)
        setWritingMode(d.writing_mode ?? null)
      })
      .catch(() => {})
  }, [])

  const save = (b: number, w: string) => {
    fetch('/api/onboarding/preferences', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bandwidth_minutes: b, writing_mode: w }),
    }).catch(() => {})
  }

  const handleBandwidth = (m: number) => {
    setBandwidth(m)
    if (writingMode) save(m, writingMode)
  }

  const handleWritingMode = (w: string) => {
    setWritingMode(w)
    if (bandwidth) save(bandwidth, w)
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xs font-black text-primary uppercase tracking-wider font-label mb-2">
          每日学习时长
        </div>
        <div className="flex gap-2">
          {[15, 25, 40].map((m) => (
            <button
              key={m}
              onClick={() => handleBandwidth(m)}
              className={`flex-1 py-2 rounded-lg text-xs font-bold font-label border-2 transition-all ${
                bandwidth === m
                  ? 'border-primary bg-primary text-white'
                  : 'border-outline-variant/30 text-on-surface'
              }`}
            >
              {m}分
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className="text-xs font-black text-primary uppercase tracking-wider font-label mb-2">
          写作目标
        </div>
        <div className="flex flex-col gap-1.5">
          {[
            { v: 'professional', l: '职场英语' },
            { v: 'ielts_task1', l: '雅思 Task 1' },
            { v: 'ielts_task2', l: '雅思 Task 2' },
          ].map((o) => (
            <button
              key={o.v}
              onClick={() => handleWritingMode(o.v)}
              className={`w-full py-2 rounded-lg text-xs font-bold font-label border-2 transition-all ${
                writingMode === o.v
                  ? 'border-primary bg-primary text-white'
                  : 'border-outline-variant/30 text-on-surface'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
