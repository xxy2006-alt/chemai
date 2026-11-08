import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'

const baseField =
  'w-full bg-surface border border-border rounded-[var(--radius-md)] px-3.5 text-sm text-ink placeholder:text-ink-muted outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:opacity-50'

export function Input({ className = '', ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${baseField} h-10 ${className}`} {...rest} />
}

export function Select({ className = '', children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={`${baseField} h-10 appearance-none cursor-pointer ${className}`} {...rest}>
      {children}
    </select>
  )
}

export function Textarea({ className = '', ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${baseField} py-2.5 min-h-[80px] resize-y ${className}`} {...rest} />
}

export function Field({
  label,
  children,
  hint,
  className = '',
}: {
  label: string
  children: React.ReactNode
  hint?: string
  className?: string
}) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-[13px] font-medium text-ink-secondary mb-1.5">{label}</span>
      {children}
      {hint && <span className="block mt-1 text-xs text-ink-muted">{hint}</span>}
    </label>
  )
}
