import type { ReactNode } from 'react'

export interface TabItem {
  key: string
  label: ReactNode
  icon?: ReactNode
  badge?: ReactNode
}

export interface TabsProps {
  items: TabItem[]
  active: string
  onChange: (key: string) => void
  /** segmented 药丸式 / underline 下划线式 */
  variant?: 'underline' | 'segmented'
  className?: string
}

export function Tabs({ items, active, onChange, variant = 'underline', className = '' }: TabsProps) {
  if (variant === 'segmented') {
    return (
      <div
        className={`inline-flex items-center gap-1 p-1 bg-surface-muted rounded-[var(--radius-md)] ${className}`}
      >
        {items.map((item) => (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-[var(--radius-sm)] text-[13px] font-medium transition-all cursor-pointer ${
              active === item.key
                ? 'bg-surface text-primary shadow-[var(--shadow-sm)]'
                : 'text-ink-secondary hover:text-ink'
            }`}
          >
            {item.icon}
            {item.label}
            {item.badge}
          </button>
        ))}
      </div>
    )
  }
  return (
    <div className={`flex items-center gap-1 border-b border-border ${className}`}>
      {items.map((item) => (
        <button
          key={item.key}
          onClick={() => onChange(item.key)}
          className={`relative flex items-center gap-1.5 px-3.5 py-2.5 text-sm font-medium transition-colors cursor-pointer ${
            active === item.key ? 'text-primary' : 'text-ink-secondary hover:text-ink'
          }`}
        >
          {item.icon}
          {item.label}
          {item.badge}
          {active === item.key && (
            <span className="absolute left-2 right-2 bottom-0 h-0.5 rounded-full bg-primary" />
          )}
        </button>
      ))}
    </div>
  )
}
