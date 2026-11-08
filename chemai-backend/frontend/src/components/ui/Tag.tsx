import type { ReactNode } from 'react'

export type TagTone = 'gray' | 'green' | 'blue' | 'red' | 'amber' | 'purple' | 'teal'

export interface TagProps {
  tone?: TagTone
  size?: 'sm' | 'md'
  children: ReactNode
  className?: string
}

const toneClasses: Record<TagTone, string> = {
  gray: 'bg-surface-muted text-ink-secondary',
  green: 'bg-success-soft text-success',
  blue: 'bg-primary-soft text-primary',
  red: 'bg-error-soft text-error',
  amber: 'bg-warning-soft text-warning',
  purple: 'bg-violet-50 text-violet-700',
  teal: 'bg-teal-soft text-teal',
}

const sizeClasses = {
  sm: 'text-[11px] px-2 py-0.5 gap-1',
  md: 'text-xs px-2.5 py-1 gap-1',
}

/** 浅色底 + 深色字标签（沿用旧设计语义色标签式呈现） */
export function Tag({ tone = 'gray', size = 'md', children, className = '' }: TagProps) {
  return (
    <span
      className={`inline-flex items-center rounded-[var(--radius-full)] font-medium whitespace-nowrap ${toneClasses[tone]} ${sizeClasses[size]} ${className}`}
    >
      {children}
    </span>
  )
}
