'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

export function MobileNav() {
  const pathname = usePathname()
  const isGeneral =
    pathname.startsWith('/learn') ||
    (typeof window !== 'undefined' && localStorage.getItem('appMode') === 'general')

  const tabs = isGeneral
    ? [{ href: '/learn', label: '课程地图', icon: 'map' }]
    : [
        { href: '/lesson', label: '课程', icon: 'menu_book' },
        { href: '/vocab', label: '生词', icon: 'style' },
      ]

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur border-t border-outline-variant/20 z-50 flex justify-around py-2">
      {tabs.map((t) => {
        const active = pathname === t.href || pathname.startsWith(t.href + '/')
        return (
          <Link
            key={t.href}
            href={t.href}
            className={`flex flex-col items-center gap-0.5 px-6 py-1 rounded-xl ${
              active ? 'text-primary' : 'text-on-surface-variant'
            }`}
          >
            <span
              className="material-symbols-outlined text-[22px]"
              style={{ fontVariationSettings: active ? "'FILL' 1" : "'FILL' 0" }}
            >
              {t.icon}
            </span>
            <span className="text-[10px] font-bold font-label">{t.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
