import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { clubService } from '../services/clubService'
import type { Club, MembershipMember } from '../domain/types'
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusBadge, SuccessNote } from '../components/ui'
import { formatDate } from '../lib/format'

type MembershipTab = 'requested' | 'active' | 'all'

export default function ManageClubPage() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const paramClubId = searchParams.get('club_id')

  const [clubs, setClubs] = useState<Club[]>([])
  const [loadingClubs, setLoadingClubs] = useState(true)
  const [selectedClubId, setSelectedClubId] = useState<number | null>(
    paramClubId ? Number(paramClubId) : null,
  )

  const [activeTab, setActiveTab] = useState<MembershipTab>('requested')
  const [members, setMembers] = useState<MembershipMember[]>([])
  const [loadingMembers, setLoadingMembers] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [actionBusyId, setActionBusyId] = useState<number | null>(null)

  // 1. Fetch clubs managed by current user (or all clubs if Administrator)
  useEffect(() => {
    let cancelled = false
    setLoadingClubs(true)
    setError(null)

    clubService
      .getClubs({ page_size: 100 })
      .then((res) => {
        if (cancelled) return
        const allClubs = res.items || []
        const isAdmin = user?.role === 'Administrator'

        // Filter clubs: admins see all; managers see their assigned clubs
        const manageable = isAdmin
          ? allClubs
          : allClubs.filter(
              (c) => c.manager_user_id === user?.user_id || user?.role === 'Club Manager',
            )

        setClubs(manageable)

        if (manageable.length > 0) {
          // If targeted club_id matches one of the manageable clubs, select it;
          // otherwise default to the first manageable club
          const found = paramClubId ? manageable.find((c) => c.club_id === Number(paramClubId)) : null
          setSelectedClubId(found ? found.club_id : manageable[0].club_id)
        } else {
          setSelectedClubId(null)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load clubs.')
      })
      .finally(() => {
        if (!cancelled) setLoadingClubs(false)
      })

    return () => {
      cancelled = true
    }
  }, [user, paramClubId])

  // Synchronize URL param when selectedClubId changes
  const handleSelectClub = (id: number) => {
    setSelectedClubId(id)
    setSearchParams({ club_id: String(id) }, { replace: true })
    setSuccessMessage(null)
    setError(null)
  }

  // 2. Fetch membership records for the selected club & tab
  const fetchMembers = useCallback(async () => {
    if (!selectedClubId) {
      setMembers([])
      return
    }

    setLoadingMembers(true)
    setError(null)

    try {
      const statusParam = activeTab === 'all' ? undefined : activeTab
      const res = await clubService.getClubMembers(selectedClubId, statusParam, 1, 100)
      setMembers(res.items || [])
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load club members.')
      setMembers([])
    } finally {
      setLoadingMembers(false)
    }
  }, [selectedClubId, activeTab])

  useEffect(() => {
    void fetchMembers()
  }, [fetchMembers])

  // 3. Handle Approve / Reject actions
  const handleUpdateStatus = async (
    member: MembershipMember,
    newStatus: 'active' | 'removed',
    role: string = 'Member',
  ) => {
    if (!selectedClubId) return
    setActionBusyId(member.membership_id)
    setError(null)
    setSuccessMessage(null)

    try {
      await clubService.updateMembershipStatus(selectedClubId, member.membership_id, {
        status: newStatus,
        role: newStatus === 'active' ? role : undefined,
      })

      const actionLabel = newStatus === 'active' ? 'Approved' : 'Rejected'
      setSuccessMessage(
        `${actionLabel} membership request for ${member.full_name} (${member.email}).`,
      )

      // Instantly update local state
      if (activeTab === 'requested') {
        setMembers((prev) => prev.filter((m) => m.membership_id !== member.membership_id))
      } else {
        setMembers((prev) =>
          prev.map((m) =>
            m.membership_id === member.membership_id
              ? { ...m, status: newStatus, role: newStatus === 'active' ? role : m.role }
              : m,
          ),
        )
      }

      // Update club member count locally if approved
      if (newStatus === 'active') {
        setClubs((prev) =>
          prev.map((c) =>
            c.club_id === selectedClubId
              ? { ...c, member_count: (c.member_count ?? 0) + 1 }
              : c,
          ),
        )
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : `Failed to ${newStatus === 'active' ? 'approve' : 'reject'} membership request.`,
      )
    } finally {
      setActionBusyId(null)
    }
  }

  const selectedClub = clubs.find((c) => c.club_id === selectedClubId)
  const pendingCount = activeTab === 'requested' ? members.length : 0

  return (
    <div>
      <PageHeader
        title="Club Management"
        icon="👥"
        subtitle="Review membership applications, approve prospective members, and manage your club roster."
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {successMessage && <div className="mb-4"><SuccessNote message={successMessage} /></div>}

      {loadingClubs ? (
        <div className="py-12 flex justify-center">
          <Spinner label="Loading managed clubs" />
        </div>
      ) : clubs.length === 0 ? (
        <div className="editorial-card p-8 text-center sm:p-12">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-vanilla text-2xl text-bean">
            🏛️
          </div>
          <h2 className="text-xl font-bold text-bean">No Managed Clubs Found</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-olive">
            Your account ({user?.email}) is not currently designated as the manager of any club. Club manager roles are assigned by university administrators or faculty advisors.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link
              to="/clubs"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blood px-4 py-2 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-blood/90"
            >
              Browse Campus Clubs ↗
            </Link>
            <Link
              to="/applyclub"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-rose/30 bg-white px-4 py-2 text-xs font-bold uppercase tracking-wider text-bean transition hover:bg-vanilla/50"
            >
              Propose a New Club
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Club Selector Bar */}
          <div className="editorial-toolbar flex-col items-start gap-4 sm:flex-row sm:items-center">
            <div className="flex w-full flex-col gap-1 sm:w-auto">
              <label htmlFor="club-select" className="editorial-label">
                Managing Club
              </label>
              <select
                id="club-select"
                value={selectedClubId ?? ''}
                onChange={(e) => handleSelectClub(Number(e.target.value))}
                className="editorial-field min-w-[280px] font-semibold text-bean"
              >
                {clubs.map((c) => (
                  <option key={c.club_id} value={c.club_id}>
                    {c.name} ({c.program_name ?? 'General'}) — {c.member_count ?? 0} members
                  </option>
                ))}
              </select>
            </div>

            {selectedClub && (
              <div className="flex flex-wrap items-center gap-4 text-xs text-olive sm:ml-auto">
                <div>
                  <span className="editorial-label block">Status</span>
                  <StatusBadge status={selectedClub.status} />
                </div>
                <div>
                  <span className="editorial-label block">Roster</span>
                  <span className="font-semibold text-bean">{selectedClub.member_count ?? 0} members</span>
                </div>
                <div>
                  <span className="editorial-label block">Chartered</span>
                  <span className="font-semibold text-bean">{formatDate(selectedClub.created_at)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Tab Navigation */}
          <div className="mb-4 mt-6 flex flex-wrap items-center justify-between gap-3 border-b border-rose/30 pb-3">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setActiveTab('requested')
                  setSuccessMessage(null)
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'requested'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>Pending Requests</span>
                {activeTab === 'requested' && (
                  <span className="rounded-full bg-white/20 px-1.5 py-0.2 text-[10px]">
                    {pendingCount}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveTab('active')
                  setSuccessMessage(null)
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'active'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>Active Members</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveTab('all')
                  setSuccessMessage(null)
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'all'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>All History</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => void fetchMembers()}
              disabled={loadingMembers}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose/30 bg-white px-3 py-1.5 text-xs font-semibold text-olive transition hover:text-bean hover:border-blood/40 cursor-pointer disabled:opacity-50"
            >
              <svg
                className={`h-3.5 w-3.5 ${loadingMembers ? 'animate-spin' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh
            </button>
          </div>

          {/* Members / Requests List */}
          {loadingMembers ? (
            <div className="py-12 flex justify-center">
              <Spinner label={`Loading ${activeTab === 'requested' ? 'membership requests' : 'members'}`} />
            </div>
          ) : members.length === 0 ? (
            <EmptyState
              title={
                activeTab === 'requested'
                  ? 'No pending membership requests'
                  : activeTab === 'active'
                  ? 'No active members found'
                  : 'No member history for this club'
              }
              hint={
                activeTab === 'requested'
                  ? 'All membership applications have been reviewed. When new students click "Join the club", their requests will appear here.'
                  : undefined
              }
            />
          ) : (
            <div className="space-y-3">
              {members.map((member) => {
                const isBusy = actionBusyId === member.membership_id
                const isPending = member.status === 'requested'

                return (
                  <article
                    key={member.membership_id}
                    className="editorial-card flex flex-col justify-between gap-4 p-4 transition sm:flex-row sm:items-center sm:p-5"
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-rose/30 bg-vanilla/60 font-serif text-sm font-bold text-blood">
                        {member.full_name
                          .split(' ')
                          .map((p) => p[0])
                          .slice(0, 2)
                          .join('')
                          .toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="truncate text-base font-bold text-bean">
                            {member.full_name}
                          </h3>
                          <StatusBadge status={member.status} />
                          {member.role && member.role !== 'Member' && (
                            <span className="rounded bg-blood/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blood">
                              {member.role}
                            </span>
                          )}
                        </div>
                        <p className="truncate text-xs text-olive">{member.email}</p>
                        <p className="mt-1 text-[11px] text-olive/80">
                          {isPending ? 'Requested' : 'Joined'}: {formatDate(member.joined_at)}
                        </p>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2.5 shrink-0 self-end sm:self-center">
                      {isPending ? (
                        <>
                          <button
                            type="button"
                            disabled={isBusy}
                            onClick={() => void handleUpdateStatus(member, 'active', 'Member')}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-olive/30 bg-olive/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-olive transition hover:bg-olive hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-olive disabled:opacity-50 cursor-pointer"
                          >
                            {isBusy ? (
                              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-olive border-t-transparent" />
                            ) : (
                              <span>✓</span>
                            )}
                            Approve
                          </button>

                          <button
                            type="button"
                            disabled={isBusy}
                            onClick={() => void handleUpdateStatus(member, 'removed')}
                            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-blood/30 bg-blood/5 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-blood transition hover:bg-blood hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood disabled:opacity-50 cursor-pointer"
                          >
                            {isBusy ? (
                              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-blood border-t-transparent" />
                            ) : (
                              <span>✕</span>
                            )}
                            Reject
                          </button>
                        </>
                      ) : member.status === 'active' ? (
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => void handleUpdateStatus(member, 'removed')}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-rose/30 bg-white px-3 py-1.5 text-xs font-medium text-olive transition hover:border-blood/30 hover:bg-blood/5 hover:text-blood disabled:opacity-50 cursor-pointer"
                          title="Remove from club roster"
                        >
                          Remove
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() => void handleUpdateStatus(member, 'active', 'Member')}
                          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-olive/30 bg-white px-3 py-1.5 text-xs font-medium text-olive transition hover:bg-olive hover:text-white disabled:opacity-50 cursor-pointer"
                          title="Re-activate membership"
                        >
                          Re-activate
                        </button>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
