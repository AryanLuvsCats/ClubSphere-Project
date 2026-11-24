import type { ReactNode } from 'react'

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-olive">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-blood border-t-transparent" />
      <span>{label}…</span>
    </div>
  )
}

export function SkeletonCard({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`skeleton-card ${compact ? 'skeleton-card-compact' : ''}`} aria-hidden="true">
      <div className="skeleton-shimmer h-3 w-1/3" />
      <div className="skeleton-shimmer mt-5 h-6 w-3/4" />
      <div className="skeleton-shimmer mt-3 h-3 w-full" />
      <div className="skeleton-shimmer mt-2 h-3 w-5/6" />
      {!compact && <div className="skeleton-shimmer mt-7 h-10 w-32" />}
    </div>
  )
}

export function SkeletonGrid({ count = 4, compact = false }: { count?: number; compact?: boolean }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" aria-label="Loading content" aria-busy="true">
      {Array.from({ length: count }, (_, index) => <SkeletonCard key={index} compact={compact} />)}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="break-words rounded-xl border border-blood/30 bg-blood/10 px-4 py-3 text-sm text-blood">
      {message}
    </div>
  )
}

export function SuccessNote({ message }: { message: string }) {
  return (
    <div className="break-words rounded-xl border border-olive/30 bg-olive/10 px-4 py-3 text-sm text-olive">
      {message}
    </div>
  )
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-rose/30 bg-white px-6 py-14 text-center">
      <p className="text-sm font-semibold text-bean">{title}</p>
      {hint && <p className="mt-1 text-xs text-olive">{hint}</p>}
    </div>
  )
}

const BADGE_STYLES: Record<string, string> = {
  active: 'bg-olive/10 text-olive border-olive/30',
  published: 'bg-olive/10 text-olive border-olive/30',
  approved: 'bg-olive/10 text-olive border-olive/30',
  confirmed: 'bg-olive/10 text-olive border-olive/30',
  requested: 'bg-rose/10 text-rose border-rose/30',
  submitted: 'bg-rose/10 text-rose border-rose/30',
  pending: 'bg-rose/10 text-rose border-rose/30',
  draft: 'bg-rose/10 text-bean border-rose/30',
  completed: 'bg-blood/10 text-blood border-blood/30',
  changes_requested: 'bg-rose/10 text-rose border-rose/30',
  cancelled: 'bg-rose/10 text-olive border-rose/30',
  removed: 'bg-blood/10 text-blood border-blood/30',
  rejected: 'bg-blood/10 text-blood border-blood/30',
  suspended: 'bg-blood/10 text-blood border-blood/30',
}

export function StatusBadge({ status }: { status: string }) {
  const style = BADGE_STYLES[status] ?? 'bg-rose/10 text-bean border-rose/30'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${style}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function PageHeader({ title, subtitle, icon }: { title: string; subtitle?: string; icon?: ReactNode }) {
  return (
    <header className="page-heading">
      <div className="page-heading-topline">
        <span className="page-kicker">ClubSphere <span aria-hidden="true">/</span> Campus life</span>
        {icon && <span className="page-heading-mark" aria-hidden="true">{icon}</span>}
      </div>
      <h1 className="page-title">{title}</h1>
      {subtitle && <p className="page-subtitle">{subtitle}</p>}
    </header>
  )
}
