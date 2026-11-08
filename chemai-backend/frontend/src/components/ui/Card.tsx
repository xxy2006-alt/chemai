import type { HTMLAttributes, ReactNode } from 'react'

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: ReactNode
  action?: ReactNode
  /** hover 轻抬升 */
  hoverable?: boolean
  /** 无内边距（表格等场景） */
  flush?: boolean
  padding?: string
}

export function Card({
  title,
  action,
  hoverable,
  flush,
  padding = 'p-5',
  className = '',
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={`bg-surface border border-border rounded-[var(--radius-lg)] shadow-[var(--shadow-sm)] ${
        hoverable
          ? 'transition-all duration-[var(--duration-normal)] hover:shadow-[var(--shadow-md)] hover:-translate-y-0.5'
          : ''
      } ${className}`}
      {...rest}
    >
      {(title || action) && (
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          {title && <h3 className="text-[15px] font-semibold text-ink m-0">{title}</h3>}
          {action}
        </div>
      )}
      <div className={flush ? '' : padding}>{children}</div>
    </div>
  )
}
