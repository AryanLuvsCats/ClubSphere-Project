import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useClubs } from '../hooks/useClubs'
import { formatDate } from '../lib/format'
import ProgramSelector from '../components/ProgramSelector'
import { EmptyState, ErrorNote, PageHeader, SkeletonGrid, StatusBadge } from '../components/ui'

export default function ClubsPage() {
  const { user } = useAuth()
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
    membershipStatusByClub,
  } = useClubs()

  return (
    <div>
      <PageHeader
        title="Clubs"
        icon="🏛️"
        subtitle="Browse every chartered student organisation at the university, along with its program, faculty manager and current membership."
      />

      <div className="editorial-toolbar gazette-toolbar">
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
        <SkeletonGrid count={6} compact />
      ) : !error && clubs.length === 0 ? (
        <EmptyState
          title="No clubs found"
          hint="Try a different search term, or head to “Apply for club” to propose a new one."
        />
      ) : (
        <>
        <div className="gazette-section-heading">
          <div><p className="editorial-label">Classified &amp; charter columns</p><h2>Clubs directory</h2></div>
          <p className="gazette-count">{clubs.length} {clubs.length === 1 ? 'organisation' : 'organisations'} on record</p>
        </div>
        <div className="gazette-club-grid">
          {clubs.map((club) => (
            <article
              key={club.club_id}
              className="gazette-club-notice flex h-full min-h-64 flex-col justify-between p-5 sm:p-6"
            >
              <div>
                <div className="gazette-club-rubric mb-4 flex items-center justify-between gap-3 pb-2">
                  <span className="editorial-label">{club.program_name || 'Campus charter'}</span>
                  <StatusBadge status={club.status} />
                </div>

                <Link to={`/clubs/${club.club_id}`} className="block text-left transition hover:text-blood focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood">
                  <h2 className="text-2xl font-semibold leading-tight text-bean hover:text-blood">{club.name}</h2>
                </Link>
                <p className="gazette-club-description mt-3 line-clamp-3 text-sm leading-relaxed text-olive">
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

                <p className="gazette-club-editor mt-3 text-xs text-olive">Charter steward <span className="font-semibold text-bean">{club.manager_name ?? '—'}</span></p>
              </div>

              <div className="gazette-club-actions mt-5 flex items-center justify-between pt-4">
                <span className="text-[10px] font-bold uppercase tracking-[.16em] text-olive">Charter No. {String(club.club_id).padStart(3, '0')}</span>
                <div className="flex items-center gap-2">
                  {(user?.role === 'Administrator' ||
                    (user?.role === 'Club Manager' && user.user_id === club.manager_user_id)) && (
                    <Link
                      to={`/manage-club?club_id=${club.club_id}`}
                      className="inline-flex min-h-10 items-center gap-1.5 border border-olive/30 bg-vanilla/40 px-3 py-2 text-xs font-bold uppercase tracking-wide text-bean transition hover:bg-olive hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-olive"
                    >
                      Manage ⚙️
                    </Link>
                  )}
                  <Link
                    to={`/clubs/${club.club_id}`}
                    className="editorial-button inline-flex min-h-10 items-center border border-bean/30 px-3 py-2 text-xs font-bold uppercase tracking-wide text-bean transition hover:border-blood hover:text-blood hover:bg-vanilla/40"
                  >
                    Club Details
                  </Link>
                  {membershipStatusByClub[club.club_id] === 'active' ? (
                    <button type="button" disabled className="editorial-button inline-flex min-h-10 items-center gap-2 border border-olive/30 bg-olive/10 px-3 py-2 text-xs font-bold uppercase tracking-wide text-olive disabled:cursor-not-allowed">✓ Active member</button>
                  ) : ['requested', 'pending'].includes(membershipStatusByClub[club.club_id] ?? '') ? (
                    <button type="button" disabled className="editorial-button inline-flex min-h-10 items-center gap-2 border border-rose/30 bg-vanilla px-3 py-2 text-xs font-bold uppercase tracking-wide text-olive disabled:cursor-not-allowed">✓ Request sent</button>
                  ) : (
                    <Link to={`/joinclub?club_id=${club.club_id}`} className="inline-flex min-h-10 items-center gap-2 border border-blood px-3 py-2 text-xs font-bold uppercase tracking-wide text-blood transition hover:bg-blood hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood">Join the club <span aria-hidden="true">↗</span></Link>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
        </>
      )}
    </div>
  )
}
