import type { ReactNode } from 'react'

export interface StatCardProps {
  label: string
  value: ReactNode
  /** 单位/后缀（如 "人"、"分"） */
  suffix?: string
  /** 状态色：normal / ok / warn / danger */
  tone?: 'normal' | 'ok' | 'warn' | 'danger'
  hint?: ReactNode
  icon?: ReactNode
}

const toneClasses = {
  normal: 'text-ink',
  ok: 'text-success',
  warn: 'text-warning',
  danger: 'text-error',
}

export function StatCard({ label, value, suffix, tone = 'normal', hint, icon }: StatCardProps) {
  return (
    <div className="relative bg-surface border border-border rounded-[var(--radius-lg)] p-5 shadow-[var(--shadow-sm)] overflow-hidden">
      {icon && <div className="absolute top-4 right-4 text-ink-muted/60">{icon}</div>}
      <div className={`kpi-number text-[28px] font-semibold leading-none ${toneClasses[tone]}`}>
        {value}
        {suffix && <span className="ml-1 text-[13px] font-normal text-ink-muted">{suffix}</span>}
      </div>
      <div className="mt-2 text-xs text-ink-secondary">{label}</div>
      {hint && <div className="mt-1 text-[11px] text-ink-muted">{hint}</div>}
    </div>
  )
}
