import type { ReactNode } from 'react'

/** 页面占位（Phase 1/2 迁移完成前使用） */
export function PlaceholderPage({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children?: ReactNode
}) {
  return (
    <div className="animate-fade-in-up">
      <div className="mb-6">
        <h1 className="text-[22px] font-semibold text-ink m-0">{title}</h1>
        <p className="mt-1 text-sm text-ink-secondary">{description}</p>
      </div>
      <div className="bg-surface border border-dashed border-border-strong rounded-[var(--radius-lg)] p-10 text-center text-sm text-ink-muted">
        {children ?? '此页面将在后续阶段迁移，敬请期待'}
      </div>
    </div>
  )
}
