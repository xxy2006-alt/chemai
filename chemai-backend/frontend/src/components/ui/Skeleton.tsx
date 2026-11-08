export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`rounded-[var(--radius-sm)] bg-surface-muted animate-pulse ${className}`} />
  )
}

export function SkeletonText({ lines = 3, className = '' }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2.5 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-3.5 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-surface border border-border rounded-[var(--radius-lg)] p-5 ${className}`}>
      <Skeleton className="h-4 w-1/3 mb-4" />
      <SkeletonText lines={3} />
    </div>
  )
}
