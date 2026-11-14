import { useSearchParams } from 'react-router-dom'
import { useJoinClub } from '../hooks/useJoinClub'
import { EmptyState, ErrorNote, PageHeader, Spinner, StatusBadge } from '../components/ui'

export default function JoinClubPage() {
  const [searchParams] = useSearchParams()
  const targetedClubId = searchParams.get('club_id')

  const {
    clubs,
    search,
    setSearch,
    loading,
    error,
    busyClubId,
    joinState,
    requestedClubIds,
    requestToJoin,
  } = useJoinClub(targetedClubId)

  return (
    <div>
      <PageHeader
        title="Join club"
        icon="🤝"
        subtitle="Send a membership request to any active club. Your request goes to the club manager, who approves or rejects it — you will be notified either way."
      />

      <div className="editorial-toolbar">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search active clubs…"
          className="editorial-field w-full sm:max-w-sm"
        />
        <p className="text-xs text-olive sm:ml-auto">Choose a community to send a membership request.</p>
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <Spinner label="Loading clubs" />
      ) : !error && clubs.length === 0 ? (
        <EmptyState
          title="No active clubs available"
          hint="There are no clubs open for membership requests right now."
        />
      ) : (
        <>
        <div className="mb-3 flex items-center justify-between border-b border-rose/30 pb-2">
          <p className="editorial-label">Open membership requests</p>
          <p className="text-xs text-olive">{clubs.length} active {clubs.length === 1 ? 'club' : 'clubs'}</p>
        </div>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {clubs.map((club) => {
            const state = joinState[club.club_id]
            const isTargeted = targetedClubId && String(club.club_id) === targetedClubId
            const isRequested = requestedClubIds.has(club.club_id)

            return (
              <div
                key={club.club_id}
                className={`editorial-card p-5 sm:p-6 ${
                  isTargeted
                    ? 'border-blood/60 bg-[#fffaf5] ring-1 ring-blood/20'
                    : ''
                }`}
              >
                <div className="mb-3 flex items-center justify-between border-b border-rose/25 pb-2">
                  <span className="editorial-label">Membership invitation</span>
                  <div className="flex items-center gap-2">
                      <StatusBadge status={club.status} />
                      {isTargeted && (
                        <span className="bg-blood/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-blood">
                          Selected
                        </span>
                      )}
                  </div>
                </div>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                  <div className="min-w-0">
                    <h2 className="text-2xl font-semibold leading-tight text-bean">{club.name}</h2>
                    <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-blood">
                      {club.program_name ?? 'Unassigned program'}
                    </p>
                    {club.description?.trim() && (
                      <p className="mt-3 line-clamp-2 max-w-2xl text-sm leading-relaxed text-olive">{club.description}</p>
                    )}
                    <p className="mt-4 border-t border-rose/25 pt-3 text-xs text-olive">
                      {club.member_count ?? 0} member{(club.member_count ?? 0) === 1 ? '' : 's'}
                      <span className="mx-2 text-rose">/</span> Convened by <span className="font-semibold text-bean">{club.manager_name ?? '—'}</span>
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() => void requestToJoin(club)}
                    disabled={busyClubId === club.club_id || isRequested}
                    className={`editorial-button min-h-10 shrink-0 px-4 py-2 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood disabled:cursor-not-allowed ${
                      isRequested
                        ? 'border border-olive/30 bg-olive/10 text-olive'
                        : 'bg-blood text-white hover:bg-bean cursor-pointer'
                    }`}
                  >
                    {busyClubId === club.club_id
                      ? 'Sending…'
                      : isRequested
                        ? '✓ Request sent'
                        : 'Request to join'}
                  </button>
                </div>

                {state && (
                  <p
                    className={`mt-3 text-xs font-medium ${
                      state.kind === 'error' ? 'text-blood' : 'text-olive'
                    }`}
                  >
                    {state.message}
                  </p>
                )}
              </div>
            )
          })}
        </div>
        </>
      )}
    </div>
  )
}
