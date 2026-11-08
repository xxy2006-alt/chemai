import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'btn-gradient shadow-[0_2px_10px_rgb(13_115_119/0.28)] hover:shadow-[0_4px_16px_rgb(13_115_119/0.38)] active:scale-[0.98]',
  secondary:
    'bg-surface text-ink border border-border hover:border-border-strong hover:bg-surface-muted active:scale-[0.98]',
  ghost: 'bg-transparent text-ink-secondary hover:bg-surface-muted active:scale-[0.98]',
  danger: 'bg-error text-white hover:bg-error/90 shadow-sm active:scale-[0.98]',
  ai: 'bg-teal text-white hover:bg-teal-hover shadow-sm active:scale-[0.98]',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-[13px] gap-1.5 rounded-[var(--radius-sm)]',
  md: 'h-10 px-4 text-sm gap-2 rounded-[var(--radius-md)]',
  lg: 'h-11 px-6 text-[15px] gap-2 rounded-[var(--radius-md)]',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, disabled, className = '', children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium transition-all duration-[var(--duration-fast)] disabled:opacity-40 disabled:pointer-events-none cursor-pointer select-none ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...rest}
    >
      {loading && <Loader2 size={size === 'sm' ? 14 : 16} className="animate-spin" />}
      {children}
    </button>
  )
})
