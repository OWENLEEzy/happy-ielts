'use client'
import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { getRandomDogUrl } from '@/lib/constants'

export function Header({ streak = 0 }: { streak?: number }) {
  const pathname = usePathname()
  const [logoUrl] = useState(getRandomDogUrl)
  const [avatarUrl] = useState(getRandomDogUrl)

  return (
    <header className="sticky top-0 z-50 bg-background/90 backdrop-blur-md border-b border-outline-variant/20">
      <div className="flex items-center justify-between max-w-5xl mx-auto px-6 py-3 gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-9 h-9 rounded-full overflow-hidden border-2 border-primary/30 flex-shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={logoUrl} className="w-full h-full object-cover" alt="logo" />
          </div>
          <span className="text-lg font-black text-primary tracking-tighter font-headline hidden sm:block">
            DynamicLingo
          </span>
        </div>

        {/* Nav links (desktop) */}
        <nav className="hidden md:flex items-center gap-1">
          {[
            { href: '/lesson', label: '今日课程' },
            { href: '/onboarding', label: '重新设置' },
          ].map(({ href, label }) => (
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

        {/* Right */}
        <div className="flex items-center gap-3">
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
          <div className="w-9 h-9 rounded-full overflow-hidden border-2 border-primary/30">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={avatarUrl} className="w-full h-full object-cover" alt="我" />
          </div>
        </div>
      </div>
    </header>
  )
}
