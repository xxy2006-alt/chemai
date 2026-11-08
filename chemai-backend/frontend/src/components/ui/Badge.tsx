import type { ReactNode } from 'react'

export type BadgeStatus = 'pass' | 'warning' | 'blocked' | 'running' | 'idle'

export interface BadgeProps {
  status: BadgeStatus
  label: ReactNode
  className?: string
}

const statusClasses: Record<BadgeStatus, { dot: string; text: string }> = {
  pass: { dot: 'bg-success', text: 'text-success bg-success-soft' },
  warning: { dot: 'bg-warning', text: 'text-warning bg-warning-soft' },
  blocked: { dot: 'bg-error', text: 'text-error bg-error-soft' },
  running: { dot: 'bg-teal animate-pulse', text: 'text-teal bg-teal-soft' },
  idle: { dot: 'bg-ink-muted', text: 'text-ink-secondary bg-surface-muted' },
}

/** 状态点 + 浅底深字标签（审核 pass/warning/blocked、工具运行状态等） */
export function Badge({ status, label, className = '' }: BadgeProps) {
  const s = statusClasses[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[var(--radius-full)] px-2.5 py-1 text-xs font-medium ${s.text} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {label}
    </span>
  )
}
