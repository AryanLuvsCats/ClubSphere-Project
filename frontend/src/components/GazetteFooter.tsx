import { Link } from 'react-router-dom'

export default function GazetteFooter() {
  const year = new Date().getFullYear()

  return (
    <footer className="gazette-footer">
      <div className="gazette-footer-inner">
        <div className="gazette-footer-brand">
          <img src="/clubsphere-logo.svg" alt="" className="h-11 w-11" />
          <div>
            <p className="gazette-footer-name">ClubSphere</p>
            <p className="gazette-footer-tagline">The campus, in orbit.</p>
          </div>
        </div>
        <section>
          <h2>Latest dispatches</h2>
          <Link to="/events">Campus events</Link>
          <Link to="/clubs">Student stories</Link>
        </section>
        <section>
          <h2>University charter</h2>
          <Link to="/applyclub">Propose a club</Link>
          <Link to="/joinclub">Membership desk</Link>
        </section>
        <section>
          <h2>Campus directory</h2>
          <Link to="/clubs">Clubs directory</Link>
          <Link to="/events">Events calendar</Link>
        </section>
      </div>
      <div className="gazette-footer-bottom">
        <span>© {year} ClubSphere · University edition</span>
        <span>Printed for campus life</span>
      </div>
    </footer>
  )
}
