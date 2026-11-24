import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useClubs } from '../hooks/useClubs'
import { clubService } from '../services/clubService'
import type { ClubPublicProfile } from '../domain/types'
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
  const [detailClub, setDetailClub] = useState<ClubPublicProfile | null>(null)
  const [detailClubId, setDetailClubId] = useState<number | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  async function openClubDetails(clubId: number) {
    setDetailClubId(clubId)
    setDetailClub(null)
    setDetailError(null)
    setDetailLoading(true)
    try {
      setDetailClub(await clubService.getClubPublicProfile(clubId))
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Could not load club details.')
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (detailClubId === null) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDetailClubId(null)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [detailClubId, detailLoading])

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

                <button type="button" onClick={() => void openClubDetails(club.club_id)} className="block text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood">
                  <h2 className="text-2xl font-semibold leading-tight text-bean">{club.name}</h2>
                </button>
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
                  <button type="button" onClick={() => void openClubDetails(club.club_id)} className="inline-flex min-h-10 items-center border border-bean/30 px-3 py-2 text-xs font-bold uppercase tracking-wide text-bean hover:border-blood hover:text-blood">Details</button>
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

      {detailClubId !== null && (
        <div className="club-detail-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setDetailClubId(null) }}>
          <section className="club-detail-panel" role="dialog" aria-modal="true" aria-labelledby="club-detail-title">
            <button ref={closeButtonRef} type="button" className="club-detail-close" onClick={() => setDetailClubId(null)} aria-label="Close club details">×</button>
            {detailLoading ? <SkeletonGrid count={1} compact /> : detailError ? <ErrorNote message={detailError} /> : detailClub && (
              <>
                <p className="editorial-label">Club charter · {detailClub.program_name || 'Campus society'}</p>
                <h2 id="club-detail-title" className="club-detail-title">{detailClub.name}</h2>
                <p className="club-detail-description">{detailClub.description || 'No description has been added to this club profile yet.'}</p>
                <div className="club-detail-stats"><strong>{detailClub.member_count ?? 0}</strong><span>active members</span></div>
                <div className="club-detail-columns">
                  <section><h3>Faculty convener</h3><p>{detailClub.faculty_convener || 'No faculty convener is listed on this club profile.'}</p></section>
                  <section><h3>Leadership roster</h3>
                    {detailClub.leadership_roster.length ? <ul>{detailClub.leadership_roster.map((leader) => <li key={`${leader.full_name}-${leader.role}`}><span>{leader.full_name}</span><b>{leader.role}</b></li>)}</ul> : <p>{detailClub.manager_name ? `${detailClub.manager_name} · Club Manager` : 'No leadership roster is listed yet.'}</p>}
                  </section>
                </div>
                <section className="club-detail-events"><h3>Upcoming club events</h3>
                  {detailClub.upcoming_events.length ? detailClub.upcoming_events.map((event) => <article key={event.event_id}><strong>{event.title}</strong><span>{new Date(event.event_date).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</span><span>{event.venue_text || 'Venue to be announced'}</span></article>) : <p>No upcoming published events are listed.</p>}
                </section>
                <div className="mt-6 flex gap-3"><Link className="editorial-button bg-blood px-4 py-2 text-xs font-bold uppercase text-white" to={`/joinclub?club_id=${detailClub.club_id}`}>Membership desk ↗</Link><Link className="editorial-button border border-bean/30 px-4 py-2 text-xs font-bold uppercase text-bean" to="/events">All campus events</Link></div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
