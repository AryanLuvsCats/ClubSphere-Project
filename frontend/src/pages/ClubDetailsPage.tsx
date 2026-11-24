import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { clubService } from '../services/clubService'
import type { ClubDetail } from '../domain/types'
import { ErrorNote, StatusBadge } from '../components/ui'
import { formatDate } from '../lib/format'

function DetailIcon({ kind }: { kind: 'vision' | 'people' | 'calendar' | 'award' | 'email' | 'phone' }) {
  const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 shrink-0 text-blood" {...stroke}>
      {kind === 'vision' && <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="m14 10 6-6M16 4h4v4" /></>}
      {kind === 'people' && <><circle cx="9" cy="8" r="3" /><path d="M3.5 20v-1.5a5.5 5.5 0 0 1 11 0V20M16 5.5a3 3 0 0 1 0 5.8M17 14a5 5 0 0 1 3.5 4.5v1" /></>}
      {kind === 'calendar' && <><rect x="4" y="5" width="16" height="15" rx="1" /><path d="M8 3v4m8-4v4M4 9h16M8 13h2m4 0h2m-8 3h2" /></>}
      {kind === 'award' && <><circle cx="12" cy="9" r="6" /><path d="m8.5 14-1 7 4.5-2 4.5 2-1-7M10 9l1.3 1.3L14 7.5" /></>}
      {kind === 'email' && <><rect x="3" y="5" width="18" height="14" rx="1" /><path d="m4 7 8 6 8-6" /></>}
      {kind === 'phone' && <path d="M7 3H5a2 2 0 0 0-2 2c0 8.8 7.2 16 16 16a2 2 0 0 0 2-2v-2l-5-2-2 3a14 14 0 0 1-7-7l3-2z" />}
    </svg>
  )
}

export default function ClubDetailsPage() {
  const { clubId } = useParams<{ clubId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [club, setClub] = useState<ClubDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [membershipStatus, setMembershipStatus] = useState<string | null>(null)
  const [busyJoining, setBusyJoining] = useState(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const parsedClubId = Number(clubId)

  useEffect(() => {
    if (!parsedClubId || Number.isNaN(parsedClubId)) {
      setError('Invalid club identifier.')
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    Promise.all([
      clubService.getClub(parsedClubId),
      clubService.getMyMembershipStatuses().catch(() => []),
    ])
      .then(([clubData, myStatuses]) => {
        if (cancelled) return
        setClub(clubData)
        const myStatus = myStatuses.find((s) => s.club_id === parsedClubId)?.status || null
        setMembershipStatus(myStatus)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load club details.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [parsedClubId])

  const handleJoinRequest = async () => {
    if (!club) return
    setBusyJoining(true)
    setFeedback(null)

    try {
      await clubService.requestJoinClub(club.club_id)
      setMembershipStatus('requested')
      setFeedback({
        type: 'success',
        message: `Membership request submitted for ${club.name}! The club manager will review your application.`,
      })
    } catch (err: unknown) {
      setFeedback({
        type: 'error',
        message: err instanceof Error ? err.message : 'Failed to send membership request.',
      })
    } finally {
      setBusyJoining(false)
    }
  }

  const isManagerOfClub =
    user?.role === 'Administrator' ||
    (user?.role === 'Club Manager' && user.user_id === club?.manager_user_id)

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl py-6 animate-pulse space-y-8">
        <div className="h-6 w-32 rounded bg-rose/20" />
        <div className="editorial-card p-6 sm:p-8 space-y-4">
          <div className="h-4 w-40 rounded bg-rose/20" />
          <div className="h-10 w-3/4 rounded bg-rose/20" />
          <div className="h-4 w-full rounded bg-rose/10" />
          <div className="h-4 w-2/3 rounded bg-rose/10" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="editorial-card h-64 p-6 bg-rose/10" />
          <div className="editorial-card h-64 p-6 bg-rose/10" />
        </div>
      </div>
    )
  }

  if (error || !club) {
    return (
      <div className="mx-auto max-w-4xl py-12 text-center space-y-4">
        <ErrorNote message={error || 'Club not found'} />
        <div>
          <button
            type="button"
            onClick={() => navigate('/clubs')}
            className="editorial-button border border-blood px-4 py-2 text-xs font-bold uppercase tracking-wider text-blood hover:bg-blood hover:text-white"
          >
            ← Return to Clubs Directory
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="club-profile-page mx-auto max-w-5xl pb-16">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-olive pt-2">
        <Link to="/clubs" className="font-medium hover:text-blood transition">
          ← Back to Clubs
        </Link>
        <span className="text-rose/50">/</span>
        <span className="text-bean font-semibold truncate">{club.name}</span>
      </nav>

      {/* Top Banner / Hero Card */}
      <header className="editorial-card p-6 sm:p-8 lg:p-10 relative overflow-hidden">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="space-y-3 max-w-2xl">
            <div className="flex flex-wrap items-center gap-3">
              <span className="editorial-label text-blood font-bold tracking-widest">
                {club.program_name || 'University Organisation'}
              </span>
              <StatusBadge status={club.status} />
              {club.branch_name && (
                <span className="rounded-full border border-rose/30 bg-vanilla/60 px-2.5 py-0.5 text-[10px] font-semibold text-olive uppercase">
                  {club.branch_name}
                </span>
              )}
            </div>

            <h1 className="font-serif text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-bean leading-tight">
              {club.name}
            </h1>

            {club.description && (
              <p className="text-sm sm:text-base leading-relaxed text-olive max-w-xl">
                {club.description}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-y-2 gap-x-6 pt-3 text-xs text-olive border-t border-rose/25">
              <div>
                <span className="text-olive/70 block text-[10px] uppercase font-bold tracking-wider">Active Members</span>
                <span className="font-serif text-xl font-bold text-bean">{club.member_count ?? 0}</span>
              </div>
              <div>
                <span className="text-olive/70 block text-[10px] uppercase font-bold tracking-wider">Chartered</span>
                <span className="font-medium text-bean">{formatDate(club.created_at)}</span>
              </div>
              <div>
                <span className="text-olive/70 block text-[10px] uppercase font-bold tracking-wider">Faculty Steward</span>
                <span className="font-medium text-bean">{club.manager_name || 'Assigned Manager'}</span>
              </div>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="flex flex-col sm:flex-row md:flex-col gap-3 shrink-0 self-start">
            {isManagerOfClub && (
              <Link
                to={`/manage-club?club_id=${club.club_id}`}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-olive/30 bg-vanilla/50 px-5 py-2.5 text-xs font-bold uppercase tracking-wider text-bean transition hover:bg-olive hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-olive"
              >
              Manage Club
              </Link>
            )}

            {membershipStatus === 'active' ? (
              <button
                type="button"
                disabled
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-olive/30 bg-olive/10 px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-olive cursor-default shadow-sm"
              >
                <span>✓</span> Active Member
              </button>
            ) : ['requested', 'pending'].includes(membershipStatus ?? '') ? (
              <button
                type="button"
                disabled
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-rose/40 bg-vanilla px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-olive cursor-default shadow-sm"
              >
                Request Pending
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void handleJoinRequest()}
                disabled={busyJoining}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-blood px-6 py-2.5 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-bean shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood disabled:opacity-50 cursor-pointer"
              >
                {busyJoining ? 'Submitting…' : 'Request to Join ↗'}
              </button>
            )}
          </div>
        </div>

        {feedback && (
          <div
            className={`mt-4 rounded-xl border p-3 text-xs ${
              feedback.type === 'success'
                ? 'border-olive/30 bg-olive/10 text-olive'
                : 'border-blood/30 bg-blood/10 text-blood'
            }`}
          >
            {feedback.message}
          </div>
        )}
      </header>

      {/* Section 1: Motives & Vision */}
      <section aria-labelledby="motives-heading" className="editorial-card p-5 sm:p-7 bg-[#fffcf5]">
        <div className="flex items-center gap-2.5 mb-3">
          <DetailIcon kind="vision" />
          <p id="motives-heading" className="editorial-label text-blood font-bold uppercase tracking-widest">
            Motives &amp; Strategic Vision
          </p>
        </div>
        <h2 className="font-serif text-2xl font-bold text-bean mb-4">
          What We Stand For &amp; Build Together
        </h2>
        <div className="prose prose-sm max-w-none text-bean leading-relaxed whitespace-pre-line text-sm sm:text-base">
          {club.motives ||
            'This club provides students with collaborative spaces to pioneer projects, develop industry-grade competencies, and lead peer workshops across their field of study.'}
        </div>
      </section>

      {/* Section 2: Core Leadership & Contact Directory */}
      <section aria-labelledby="leadership-heading" className="club-profile-section">
        <div className="club-profile-section-heading">
          <div className="flex items-center gap-2">
            <DetailIcon kind="people" />
            <p id="leadership-heading" className="editorial-label text-blood font-bold uppercase tracking-widest">
              Core Leadership &amp; Directory
            </p>
          </div>
          <h2 className="font-serif text-2xl font-bold text-bean">
            Meet the Club Officers &amp; Coordinators
          </h2>
        </div>

        {club.core_members && club.core_members.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {club.core_members.map((member, idx) => (
              <article
                key={`${member.email}-${idx}`}
                className="editorial-card flex min-h-44 flex-col justify-between gap-4 p-5 transition hover:border-blood/30"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center rounded-md border border-blood/20 bg-blood/5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blood">
                      {member.role}
                    </span>
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-vanilla text-xs font-bold text-blood">
                      {member.name
                        .split(' ')
                        .map((n) => n[0])
                        .slice(0, 2)
                        .join('')
                        .toUpperCase()}
                    </div>
                  </div>
                  <h3 className="text-base font-bold text-bean truncate" title={member.name}>
                    {member.name}
                  </h3>
                </div>

                <div className="space-y-1.5 pt-3 border-t border-rose/20 text-xs">
                  <a
                    href={`mailto:${member.email}`}
                    className="flex items-center gap-2 text-olive hover:text-blood transition truncate"
                    title={`Send email to ${member.email}`}
                  >
                    <DetailIcon kind="email" />
                    <span className="truncate">{member.email}</span>
                  </a>
                  {member.phone && (
                    <a
                      href={`tel:${member.phone.replace(/\s+/g, '')}`}
                      className="flex items-center gap-2 text-olive hover:text-blood transition truncate"
                      title={`Call ${member.phone}`}
                    >
                      <DetailIcon kind="phone" />
                      <span className="truncate">{member.phone}</span>
                    </a>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="club-profile-empty">No core members listed for this club yet.</div>
        )}
      </section>

      {/* Section 3: Recent Events by the Club */}
      <section aria-labelledby="events-heading" className="club-profile-section">
        <div className="club-profile-section-heading">
          <div className="flex items-center gap-2">
            <DetailIcon kind="calendar" />
            <p id="events-heading" className="editorial-label text-blood font-bold uppercase tracking-widest">
              Club Activities &amp; Timeline
            </p>
          </div>
          <h2 className="font-serif text-2xl font-bold text-bean">
            Recent &amp; Upcoming Events
          </h2>
        </div>

        {club.recent_events && club.recent_events.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {club.recent_events.map((event) => (
              <article
                key={event.event_id}
                className="editorial-card flex min-h-48 flex-col justify-between gap-4 p-5 transition hover:border-blood/30"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-blood">
                      {formatDate(event.event_date)}
                    </span>
                    <StatusBadge status={event.status} />
                  </div>
                  <h3 className="text-base font-bold text-bean leading-snug">
                    {event.title}
                  </h3>
                  {event.description && (
                    <p className="line-clamp-3 text-xs leading-relaxed text-olive">
                      {event.description}
                    </p>
                  )}
                </div>

                <div className="pt-3 border-t border-rose/20 text-xs text-olive flex items-center justify-between">
                  <span className="truncate">{event.venue_text || 'Campus Venue'}</span>
                  <Link
                    to="/events"
                    className="text-blood font-semibold hover:underline shrink-0 text-[11px]"
                  >
                    View in Calendar →
                  </Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="club-profile-empty">
            No events currently scheduled for {club.name}. Check back soon!
          </div>
        )}
      </section>

      {/* Section 4: Past Event Achievements */}
      <section aria-labelledby="achievements-heading" className="club-profile-section">
        <div className="club-profile-section-heading">
          <div className="flex items-center gap-2">
            <DetailIcon kind="award" />
            <p id="achievements-heading" className="editorial-label text-blood font-bold uppercase tracking-widest">
              Milestones &amp; Honors
            </p>
          </div>
          <h2 className="font-serif text-2xl font-bold text-bean">
            Past Event Achievements &amp; Laurels
          </h2>
        </div>

        {club.past_achievements && club.past_achievements.length > 0 ? (
          <div className="space-y-4">
            {club.past_achievements.map((ach, idx) => (
              <article
                key={`${ach.title}-${idx}`}
                className="editorial-card p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:border-blood/30"
              >
                <div className="space-y-1.5 max-w-2xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-serif text-lg font-bold text-bean">
                      {ach.title}
                    </h3>
                    {ach.date && (
                      <span className="text-xs text-olive">({ach.date})</span>
                    )}
                  </div>
                  <p className="text-sm text-olive leading-relaxed">
                    {ach.description}
                  </p>
                </div>

                {ach.award_or_highlight && (
                  <div className="shrink-0 self-start md:self-center">
                    <span className="inline-flex items-center gap-1.5 rounded-xl border border-olive/30 bg-olive/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-olive shadow-sm">
                      {ach.award_or_highlight}
                    </span>
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="club-profile-empty">
            No past achievements recorded yet for this club.
          </div>
        )}
      </section>
    </div>
  )
}
