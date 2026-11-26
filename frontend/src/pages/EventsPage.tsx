import { useEvents } from '../hooks/useEvents'
import { formatDate } from '../lib/format'
import { EmptyState, ErrorNote, PageHeader, SkeletonGrid, StatusBadge } from '../components/ui'

export default function EventsPage() {
  const {
    events,
    search,
    setSearch,
    status,
    setStatus,
    loading,
    error,
    busyEventId,
    feedback,
    registeredIds,
    toggleRegistration,
  } = useEvents()

  return (
    <div>
      <PageHeader
        title="Events"
        icon="📅"
        subtitle="Every published club event with live seat availability. Register while seats remain and before the registration deadline."
      />

      <div className="editorial-toolbar gazette-toolbar">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search events by title or venue…"
          className="editorial-field w-full sm:max-w-sm"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="editorial-field w-full sm:w-56"
        >
          <option value="published">Published</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="draft">Draft</option>
        </select>
      </div>

      {error && <ErrorNote message={error} />}

      {loading ? (
        <SkeletonGrid count={4} compact />
      ) : !error && events.length === 0 ? (
        <EmptyState title="No events found" hint="There are no events matching the current filters." />
      ) : (
        <>
        <div className="gazette-section-heading">
          <div><p className="editorial-label">Campus dispatches &amp; telegrams</p><h2>The events board</h2></div>
          <p className="gazette-count">{events.length} {events.length === 1 ? 'listing' : 'listings'}</p>
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {events.map((event, index) => {
            const filled = event.capacity > 0 ? (event.confirmed_registrations / event.capacity) * 100 : 0
            const isFull = event.seats_left <= 0
            const isRegistered = registeredIds.has(event.event_id)
            const note = feedback[event.event_id]

            return (
              <article
                key={event.event_id}
                className={`gazette-event-notice p-5 sm:p-6 ${index === 0 ? 'gazette-event-featured' : ''}`}
              >
                <div className="gazette-event-ribbon mb-4 flex items-center justify-between pb-2">
                  <span className="editorial-label">Live telegram <span className="ml-1 text-olive">No. {String(event.event_id).padStart(3, '0')}</span></span>
                  <StatusBadge status={event.status} />
                </div>
                {event.poster_url && (
                  <div className="mb-4 overflow-hidden rounded-lg border border-rose/30 bg-vanilla/30">
                    <img
                      src={event.poster_url}
                      alt={`${event.title} poster`}
                      loading="lazy"
                      className="h-44 w-full object-cover"
                    />
                  </div>
                )}
                <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <h2 className="text-2xl font-semibold leading-tight text-bean">{event.title}</h2>
                      {isRegistered && (
                        <span className="inline-flex items-center gap-1 border border-olive/30 bg-olive/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-olive">
                          ✓ You are registered
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-blood">
                      Hosted by {event.club_name ?? 'a university club'}
                    </p>
                    <p className="gazette-event-time mt-3">{new Date(event.event_date).toLocaleString('en-US', { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(',', ' ·').toUpperCase()}</p>

                    <dl className="mt-5 grid grid-cols-1 gap-x-5 gap-y-4 border-t border-rose/25 pt-4 text-xs sm:grid-cols-2">
                      <div>
                        <dt className="editorial-label">Venue</dt>
                        <dd className="mt-1 text-bean">{event.venue_text || 'To be announced'}</dd>
                      </div>
                      <div><dt className="editorial-label">Date &amp; time</dt><dd className="mt-1 font-medium text-bean">{formatDate(event.event_date)}</dd></div>
                      <div>
                        <dt className="editorial-label">Register by</dt>
                        <dd className="mt-1 text-bean">{formatDate(event.registration_deadline)}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="shrink-0 border-t border-rose/25 pt-3 sm:min-w-32 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0 sm:text-right">
                    <p className="editorial-label">Seats remaining</p>
                    <p className={`mt-1 font-serif text-4xl font-semibold leading-none ${isFull && !isRegistered ? 'text-blood' : 'text-bean'}`}>
                      {event.seats_left}
                    </p>
                    <p className="mt-1 text-xs text-olive">of {event.capacity} total</p>
                    <button
                      type="button"
                      onClick={() => void toggleRegistration(event)}
                      disabled={
                        busyEventId === event.event_id ||
                        event.status !== 'published' ||
                        (!isRegistered && isFull)
                      }
                      className={`editorial-button mt-3 min-h-10 px-4 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-olive cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood ${
                        isRegistered
                          ? 'border border-rose/40 bg-white text-blood hover:bg-blood/10'
                          : 'bg-blood text-white hover:bg-bean'
                      }`}
                    >
                      {busyEventId === event.event_id
                        ? 'Working…'
                        : isRegistered
                          ? 'Cancel registration'
                          : isFull
                            ? 'Event full'
                            : 'Register'}
                    </button>
                  </div>
                </div>

                <div className="mt-5 h-1.5 w-full overflow-hidden bg-vanilla/60">
                  <div
                    className={`h-full transition-all ${isFull ? 'bg-blood' : 'bg-olive'}`}
                    style={{ width: `${Math.min(100, filled)}%` }}
                  />
                </div>

                {note && (
                  <p
                    className={`mt-3 text-xs font-medium ${note.kind === 'error' ? 'text-blood' : 'text-olive'}`}
                  >
                    {note.message}
                  </p>
                )}
              </article>
            )
          })}
        </div>
        </>
      )}
    </div>
  )
}
