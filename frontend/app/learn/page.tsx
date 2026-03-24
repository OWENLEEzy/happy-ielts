'use client'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Link from 'next/link'
import { Header } from '@/components/Header'
import { MobileNav } from '@/components/MobileNav'
import { GL, glBtn } from '@/lib/learn-theme'

const TOPICS = ['吉他', '投资入门', '摄影构图', '烹饪', '心理学', '编程', '历史', '写作']

export default function LearnLandingPage() {
  const router = useRouter()

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: GL.bg,
        color: GL.fg,
      }}
    >
      <Header dark />

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-16 max-w-4xl mx-auto w-full">
        {/* Ambient orb */}
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 rounded-full pointer-events-none"
          style={{
            background: 'radial-gradient(circle, rgba(201,168,76,0.08) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
        />

        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="text-center space-y-6 relative z-10"
        >
          {/* Eyebrow */}
          <div
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-mono-dm tracking-widest uppercase"
            style={{
              borderColor: 'rgba(201,168,76,0.3)',
              color: GL.amber,
              background: 'rgba(201,168,76,0.06)',
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ background: GL.amber }}
            />
            AI 备课系统
          </div>

          {/* Main headline */}
          <h1
            className="font-cormorant font-light leading-none tracking-tight"
            style={{ fontSize: 'clamp(3.5rem, 9vw, 7rem)', color: GL.fg }}
          >
            掌握任何
            <br />
            <em style={{ color: GL.amber, fontStyle: 'italic' }}>你想学的</em>
          </h1>

          {/* Subtext */}
          <p
            className="max-w-md mx-auto text-base leading-relaxed opacity-60"
            style={{ fontFamily: 'Manrope, sans-serif' }}
          >
            告诉我你的目标，AI 老师为你深度备课，生成专属学习地图，一节一节带你抵达。
          </p>

          {/* CTA */}
          <motion.button
            onClick={() => router.push('/learn/onboarding')}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.98 }}
            className="inline-flex items-center gap-3 px-8 py-4 rounded-full font-medium text-sm tracking-wide transition-all"
            style={{
              ...glBtn,
              boxShadow: '0 0 40px rgba(201,168,76,0.3), 0 4px 20px rgba(0,0,0,0.4)',
            }}
          >
            开始学习
            <span style={{ fontSize: 18 }}>→</span>
          </motion.button>

          {/* Also have English mode */}
          <p className="text-xs opacity-30 font-mono-dm">
            想练英语？
            <Link href="/lesson" className="underline hover:opacity-60 transition-opacity">
              切换到英语飞轮
            </Link>
          </p>
        </motion.div>

        {/* Topic scroll strip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5, duration: 1 }}
          className="mt-20 w-full relative z-10"
        >
          <div className="flex gap-3 flex-wrap justify-center">
            {TOPICS.map((t, i) => (
              <motion.span
                key={t}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.6 + i * 0.06, duration: 0.4 }}
                className="px-4 py-2 rounded-full text-sm border cursor-default select-none"
                style={{
                  borderColor: GL.cardBorder,
                  color: 'rgba(240,235,224,0.45)',
                  background: GL.amberFaint,
                  fontFamily: 'Manrope, sans-serif',
                }}
              >
                {t}
              </motion.span>
            ))}
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.2 }}
              className="px-4 py-2 text-sm opacity-30"
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              以及一切...
            </motion.span>
          </div>
        </motion.div>

        {/* Value props */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.8 }}
          className="mt-16 grid grid-cols-3 gap-6 max-w-2xl w-full relative z-10"
        >
          {[
            { icon: '⟳', title: '深度备课', desc: 'AI 老师为你搜集数百个来源' },
            { icon: '◈', title: '专属路径', desc: '依据你的目标定制学习地图' },
            { icon: '↑', title: '持续进化', desc: '记住你的弱点，下节课重点攻克' },
          ].map((p) => (
            <div key={p.title} className="text-center space-y-2">
              <div className="text-2xl" style={{ color: GL.amber }}>
                {p.icon}
              </div>
              <div
                className="text-xs font-semibold tracking-wide uppercase font-mono-dm"
                style={{ color: 'rgba(201,168,76,0.8)' }}
              >
                {p.title}
              </div>
              <div
                className="text-xs leading-relaxed opacity-40"
                style={{ fontFamily: 'Manrope, sans-serif' }}
              >
                {p.desc}
              </div>
            </div>
          ))}
        </motion.div>
      </main>

      <MobileNav />
    </div>
  )
}
