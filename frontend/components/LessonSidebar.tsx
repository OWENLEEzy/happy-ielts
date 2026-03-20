'use client'
import type { LessonPhase } from '@/types'

const PHASES: { id: LessonPhase; label: string; icon: string }[] = [
  { id: 'review',   label: '词汇复习', icon: 'quiz' },
  { id: 'reading',  label: '深读文章', icon: 'menu_book' },
  { id: 'writing',  label: '写作任务', icon: 'edit_note' },
  { id: 'feedback', label: '批改反馈', icon: 'grade' },
]

interface Props {
  phase: LessonPhase
  articleTitle: string
}

export function LessonSidebar({ phase, articleTitle }: Props) {
  const currentIndex = PHASES.findIndex(p => p.id === phase)

  return (
    <aside className="hidden lg:flex flex-col w-52 flex-shrink-0 sticky top-16 h-[calc(100dvh-4rem)] border-r border-outline-variant/20 bg-surface-container-low/40 py-6 px-4 gap-6">
      {/* Article title */}
      <div className="px-2">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant/50 mb-1.5 font-label">
          今日文章
        </p>
        <p className="text-xs font-medium text-on-surface leading-relaxed line-clamp-3">
          {articleTitle}
        </p>
      </div>

      {/* Phase list */}
      <nav className="flex flex-col gap-1">
        {PHASES.map((p, i) => {
          const isDone = i < currentIndex
          const isCurrent = i === currentIndex
          return (
            <div
              key={p.id}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl ${
                isCurrent
                  ? 'bg-primary/10 text-primary'
                  : isDone
                  ? 'text-on-surface-variant'
                  : 'text-on-surface-variant/35'
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                  isDone
                    ? 'bg-primary/15'
                    : isCurrent
                    ? 'bg-primary'
                    : 'bg-outline-variant/30'
                }`}
              >
                <span
                  className={`material-symbols-outlined text-[12px] ${
                    isDone ? 'text-primary' : isCurrent ? 'text-white' : 'text-on-surface-variant/35'
                  }`}
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  {isDone ? 'check' : p.icon}
                </span>
              </div>
              <span className={`text-sm font-label ${isCurrent ? 'font-bold' : 'font-medium'}`}>
                {p.label}
              </span>
            </div>
          )
        })}
      </nav>

      {/* Progress bar */}
      <div className="mt-auto px-2">
        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant/50 mb-2 font-label">
          今日进度
        </p>
        <div className="h-1.5 bg-outline-variant/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500"
            style={{ width: `${((currentIndex + 1) / PHASES.length) * 100}%` }}
          />
        </div>
        <p className="text-xs text-on-surface-variant/50 mt-1.5 font-label">
          {currentIndex + 1} / {PHASES.length}
        </p>
      </div>
    </aside>
  )
}
