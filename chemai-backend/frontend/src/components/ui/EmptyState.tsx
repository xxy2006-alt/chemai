import type { ReactNode } from 'react'
import { FlaskConical } from 'lucide-react'

export interface EmptyStateProps {
  /** 插画槽：素材就位前由调用方传占位（图标/色块），缺省用默认图标 */
  illustration?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ illustration, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-12 px-6 ${className}`}>
      {illustration ? (
        <div className="mb-5">{illustration}</div>
      ) : (
        <div className="mb-5 w-24 h-24 rounded-[var(--radius-lg)] bg-surface-muted flex items-center justify-center border border-dashed border-border-strong">
          <FlaskConical size={30} className="text-ink-muted/70" aria-hidden />
        </div>
      )}
      <h3 className="text-[15px] font-semibold text-ink m-0">{title}</h3>
      {description && <p className="mt-1.5 text-[13px] text-ink-secondary max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
