import { Link } from 'react-router-dom'
import { useClubs } from '../hooks/useClubs'
import { formatDate } from '../lib/format'
import ProgramSelector from '../components/ProgramSelector'
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusBadge } from '../components/ui'

export default function ClubsPage() {
  const {
    clubs,
    search,
    setSearch,
    branchId,
    setBranchId,
    programId,
    setProgramId,
    loading,
    error,
  } = useClubs()

  return (
    <div>
      <PageHeader
        title="Clubs"
        icon="🏛️"
        subtitle="Browse every chartered student organisation at the university, along with its program, faculty manager and current membership."
      />

      <div className="editorial-toolbar">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search clubs by name or description…"
          className="editorial-field w-full sm:max-w-sm"
        />
        <div className="sm:w-96">
          <ProgramSelector
            branchId={branchId}
            programId={programId}
            onBranchChange={setBranchId}
            onProgramChange={setProgramId}
          />
        </div>
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <Spinner label="Loading clubs" />
      ) : !error && clubs.length === 0 ? (
        <EmptyState
          title="No clubs found"
          hint="Try a different search term, or head to “Apply for club” to propose a new one."
        />
      ) : (
        <>
        <div className="mb-3 flex items-center justify-between border-b border-rose/30 pb-2">
          <p className="editorial-label">The club directory</p>
          <p className="text-xs text-olive">{clubs.length} {clubs.length === 1 ? 'organisation' : 'organisations'}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {clubs.map((club) => (
            <article
              key={club.club_id}
              className="editorial-card flex min-h-64 flex-col justify-between p-5 sm:p-6"
            >
              <div>
                <div className="mb-4 flex items-center justify-between gap-3 border-b border-rose/25 pb-2">
                  <span className="editorial-label">Campus organisation</span>
                  <StatusBadge status={club.status} />
                </div>

                <h2 className="text-2xl font-semibold leading-tight text-bean">{club.name}</h2>

                <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-blood">
                  {club.program_name ?? 'Unassigned program'}
                </p>

                <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-olive">
                  {club.description?.trim() || 'No description has been provided for this club yet.'}
                </p>

                <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-rose/25 pt-4 text-xs">
                  <div>
                    <dt className="editorial-label">Members</dt>
                    <dd className="mt-1 font-serif text-2xl font-semibold text-bean">{club.member_count ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="editorial-label">Chartered</dt>
                    <dd className="mt-2 font-medium text-bean">{formatDate(club.created_at)}</dd>
                  </div>
                </dl>

                <p className="mt-3 text-xs text-olive">
                  Edited by <span className="font-semibold text-bean">{club.manager_name ?? '—'}</span>
                </p>
              </div>

              <div className="mt-5 flex items-center justify-between border-t border-rose/25 pt-4">
                <span className="text-[10px] font-bold uppercase tracking-[.16em] text-olive">Club record</span>
                <Link
                  to={`/joinclub?club_id=${club.club_id}`}
                  className="inline-flex min-h-10 items-center gap-2 border border-blood px-3 py-2 text-xs font-bold uppercase tracking-wide text-blood transition hover:bg-blood hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood"
                >
                  Join the club <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
        </>
      )}
    </div>
  )
}
