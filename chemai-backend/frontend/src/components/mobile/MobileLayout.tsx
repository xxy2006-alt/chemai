/* MobileLayout.tsx — 移动端布局壳（ADR-0001）：430 视口容器 + 主题作用域 + 槽位。
 * 主题按端注入 data-theme（mobile-themes.css 覆盖 Tailwind 变量，两端互不渗漏）。
 * R-L2：430×900 视口设计；底部安全区留白。 */

import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

export type MobileTheme = 'student' | 'parent'

export function MobileLayout({
  theme,
  header,
  footer,
  children,
  className = '',
}: {
  theme: MobileTheme
  header?: ReactNode
  footer?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div
      data-theme={theme}
      className="h-[100dvh] flex flex-col bg-bg text-ink mx-auto w-full max-w-[430px] overflow-hidden"
    >
      {header}
      <div className={`flex-1 min-h-0 overflow-y-auto ${className}`}>{children}</div>
      {footer && (
        <footer className="shrink-0 pb-[env(safe-area-inset-bottom)]">{footer}</footer>
      )}
    </div>
  )
}

/* 底部 Tab 导航（P-04：56px，激活项主色） */
export interface MobileTab {
  id: string
  label: string
  icon: ReactNode
  onClick: () => void
  active: boolean
}

export function MobileTabBar({ tabs }: { tabs: MobileTab[] }) {
  return (
    <nav className="flex bg-surface border-t border-border/60 h-14">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={t.onClick}
          className={`flex-1 flex flex-col items-center justify-center gap-0.5 text-[10px] transition-colors cursor-pointer relative ${
            t.active ? 'text-primary font-medium' : 'text-ink-muted'
          }`}
        >
          {t.active && (
            <span className="absolute top-0 left-1/2 -translate-x-1/2 w-5 h-[2.5px] rounded-b-[3px] bg-primary" />
          )}
          {t.icon}
          {t.label}
        </button>
      ))}
    </nav>
  )
}

/* 顶部标题栏（P-03 移动端 56px） */
export function MobileHeader({
  title,
  left,
  right,
  className = '',
}: {
  title: ReactNode
  left?: ReactNode
  right?: ReactNode
  className?: string
}) {
  return (
    <div className={`shrink-0 h-14 px-3 flex items-center gap-2 bg-bg border-b border-border/60 ${className}`}>
      {left}
      <div className="flex-1 min-w-0 font-semibold text-[16px] truncate">{title}</div>
      {right}
    </div>
  )
}

/* 全屏滑出面板（学习计划/报告/设置/对话等） */
export function MobileFullPane({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: ReactNode
  onClose: () => void
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-center bg-bg">
      <div className="w-full max-w-[430px] h-[100dvh] flex flex-col bg-bg">
        <MobileHeader
          title={title}
          left={
            <button
              onClick={onClose}
              className="p-1.5 -ml-1.5 rounded-[var(--radius-sm)] hover:bg-surface-muted cursor-pointer"
              aria-label="返回"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m15 18-6-6 6-6" />
              </svg>
            </button>
          }
        />
        <div className="flex-1 min-h-0 overflow-y-auto p-4 pb-[max(16px,env(safe-area-inset-bottom))]">{children}</div>
      </div>
    </div>
  )
}

/* 骨架/加载/空态（P-10 / P-11：三态 MUST，空态给行动引导 R-S2） */
export function MobileLoading({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-ink-muted text-sm">
      <Loader2 size={16} className="animate-spin" />
      {text}
    </div>
  )
}

export function MobileEmpty({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode
  title: string
  hint?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="text-center py-14 px-8">
      {icon && <div className="flex justify-center mb-3 text-ink-muted/70">{icon}</div>}
      <h3 className="text-[16px] font-semibold text-ink mb-1.5">{title}</h3>
      {hint && <p className="text-[13px] text-ink-secondary leading-relaxed">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* overscroll 背景由 mobile-themes.css 的 body:has(...) 规则处理，无需 JS */
