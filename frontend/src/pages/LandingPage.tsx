import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { eventService } from '../services/eventService'
import type { EventItem } from '../domain/types'
import NewsGlobe from '../components/NewsGlobe'
import ScrollFilm from '../components/scrollfilm/ScrollFilm'
import GazetteFooter from '../components/GazetteFooter'

/* ── editorial sections ──────────────────────────────────────────── */

function EditorialHeader() {
  const { isAuthenticated } = useAuth()
  const editionDate = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'short', day: 'numeric', year: 'numeric',
  })

  return (
    <header className="ed-header">
      <div className="ed-masthead-meta">
        <span>Vol. 01 <i>•</i> Campus Edition</span>
        <span className="ed-masthead-note">The University Gazette &amp; Activity Chronicle</span>
        <span>{editionDate}</span>
      </div>
      <div className="ed-masthead">
        <div className="ed-masthead-side">Chartered societies<br /><strong>Campus life in orbit</strong></div>
        <div className="ed-masthead-center">
          <img src="/clubsphere-logo.svg" alt="" className="ed-masthead-logo" />
          <div>
            <span className="ed-brand-name">ClubSphere</span>
          </div>
        </div>
        <div className="ed-masthead-side ed-masthead-right">University date<br /><strong>Campus dispatch</strong></div>
      </div>
      <div className="ed-header-inner">
        <nav className="ed-nav" aria-label="Campus navigation">
          <Link to="/clubs">Clubs</Link>
          <Link to="/events">Events</Link>
        </nav>
        {isAuthenticated ? (
          <Link to="/clubs" className="ed-signin">
            Enter the platform
          </Link>
        ) : (
          <Link to="/login" className="ed-signin">
            Enter the platform
          </Link>
        )}
      </div>
    </header>
  )
}

function HeroCopy() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="ed-hero-copy">
      <p className="ed-eyebrow">The university, in motion</p>
      <h1 className="ed-headline">
        Campus,
        <br />
        <em>in orbit.</em>
      </h1>
      <p className="ed-hero-intro">
        Find the people, ideas, and stories shaping student life.
      </p>
      <Link to={isAuthenticated ? '/clubs' : '/login'} className="ed-text-link">
        Enter the platform <span aria-hidden="true">→</span>
      </Link>
      <div className="ed-manifesto">
        <div>
          Different people
          <br />
          Brighter perspectives
          <br />A stronger tomorrow
        </div>
        <div>
          Student clubs
          <br />
          Club achievements
          <br />
          Real impact
        </div>
      </div>
    </div>
  )
}

function GlobeColumn() {
  return (
    <div className="ed-globe-col" id="discover">
      <div className="ed-globe-wrap">
        <span className="ed-globe-callout ed-callout-ideas">Ideas</span>
        <span className="ed-globe-callout ed-callout-people">People</span>
        <span className="ed-globe-callout ed-callout-stories">Stories</span>
        <NewsGlobe className="ed-globe-canvas" />
      </div>
    </div>
  )
}

function BriefSidebar() {
  const [today] = useState(() => new Date())
  const [events, setEvents] = useState<EventItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const dateStr = today.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  useEffect(() => {
    let cancelled = false
    eventService.getEvents({ status: 'published', page_size: 3 })
      .then((result) => {
        if (!cancelled) setEvents(result.items)
      })
      .catch(() => {
        if (!cancelled) setError('Campus events are temporarily unavailable.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  return (
    <aside className="ed-brief" id="events-brief">
      <div className="ed-brief-header">
        <h2 className="ed-brief-title">Today’s brief · Campus events</h2>
        <span className="ed-brief-date">{dateStr}</span>
      </div>
      {loading && <p className="ed-brief-state">Loading published campus events…</p>}
      {error && <p className="ed-brief-state" role="status">{error}</p>}
      {!loading && !error && events.length === 0 && (
        <p className="ed-brief-state">There are no published campus events to show right now.</p>
      )}
      {events.map((item) => (
        <article key={item.event_id} className="ed-brief-item">
          <div className="ed-brief-meta">
            <span className="ed-brief-category">{item.club_name || 'University club'}</span>
            <span className="ed-brief-time">{new Date(item.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
          </div>
          <h3 className="ed-brief-headline">{item.title}</h3>
          <dl className="ed-brief-event-details">
            <div><dt>When</dt><dd>{new Date(item.event_date).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</dd></div>
            <div><dt>Where</dt><dd>{item.venue_text || 'Venue to be announced'}</dd></div>
            <div><dt>Registration closes</dt><dd>{new Date(item.registration_deadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</dd></div>
            <div><dt>Seats left</dt><dd>{item.seats_left} of {item.capacity}</dd></div>
          </dl>
        </article>
      ))}
      <Link to="/events" className="ed-brief-more">
        Explore campus events <span aria-hidden="true">→</span>
      </Link>
    </aside>
  )
}

function EditorialFooter() {
  return <GazetteFooter />
}

/* ── main landing page ───────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <div className="landing" id="top">
      <ScrollFilm />
      <main className="editorial">
        <div className="ed-ticker" aria-label="Campus announcements">
          <span className="ed-ticker-label">Campus dispatch</span>
          <div className="ed-ticker-track"><span>Student clubs</span><i>✦</i><span>Campus events</span><i>✦</i><span>Club achievement reports</span><i>✦</i><span>Ideas, people, community</span><i aria-hidden="true">✦</i><span aria-hidden="true">Student clubs</span><i aria-hidden="true">✦</i><span aria-hidden="true">Campus events</span><i aria-hidden="true">✦</i><span aria-hidden="true">Club achievement reports</span><i aria-hidden="true">✦</i><span aria-hidden="true">Ideas, people, community</span></div>
        </div>
        <EditorialHeader />
        <section className="ed-hero" aria-label="ClubSphere introduction">
          <HeroCopy />
          <GlobeColumn />
          <BriefSidebar />
        </section>
        <EditorialFooter />
      </main>
    </div>
  )
}
