interface StatCardProps {
  label: string
  value: string | number
  hint?: string
  accent: string
}

export function StatCard({ label, value, hint, accent }: StatCardProps) {
  return (
    <div className="editorial-card relative overflow-hidden p-5">
      <span className="absolute inset-x-0 top-0 h-1 bg-blood/70" />
      <p className="editorial-label">{label}</p>
      <p className={`mt-2 font-serif text-4xl font-semibold leading-none ${accent}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-olive">{hint}</p>}
    </div>
  )
}
