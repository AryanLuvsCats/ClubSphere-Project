import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { NAV_ITEMS, ROLE_LABELS } from '../domain/constants'
import { usePendingMembershipCount } from '../hooks/usePendingMembershipCount'
import NotificationsPopover from './NotificationsPopover'
import GazetteFooter from './GazetteFooter'

function SidebarIcon({ name }: { name: string }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 shrink-0" {...common}>
      {name === 'clubs' && <><path d="M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6M3 9h18" /></>}
      {name === 'events' && <><rect x="4" y="5" width="16" height="15" rx="1" /><path d="M8 3v4m8-4v4M4 9h16M8 13h2m4 0h2m-8 3h2m4 0h2" /></>}
      {name === 'join' && <><circle cx="9" cy="8" r="3" /><path d="M3.5 20v-1.5a5.5 5.5 0 0 1 11 0V20M18 8v6m-3-3h6" /></>}
      {name === 'apply' && <><path d="M6 3h8l4 4v6M14 3v5h5M6 3v18h6" /><path d="m13 17 5-5 2 2-5 5-3 1z" /></>}
      {name === 'manage' && <><circle cx="9" cy="8" r="3" /><path d="M3.5 20v-1.5a5.5 5.5 0 0 1 11 0V20M17 7h4m-2-2v4m-2 5h4m-4 3h4" /></>}
      {name === 'admin' && <><path d="M12 3 19 6v5c0 4.5-2.8 7.8-7 10-4.2-2.2-7-5.5-7-10V6z" /><path d="m9 12 2 2 4-4" /></>}
    </svg>
  )
}

export default function Layout() {
  const { user, isAuthenticated, logout } = useAuth()
  const pendingRequestCount = usePendingMembershipCount(user)
  const navigate = useNavigate()

  const [menuOpen, setMenuOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const sidebarRef = useRef<HTMLElement>(null)

  const initials = (user?.full_name ?? '?')
    .split(' ')
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()

  // Manage modal accessibility, scroll lock, keyboard trap, and Escape key
  useEffect(() => {
    if (!menuOpen) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        menuButtonRef.current?.focus()
        return
      }
      if (event.key !== 'Tab') return

      const focusable = sidebarRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled])',
      )
      if (!focusable || focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [menuOpen])

  function closeMenu() {
    setMenuOpen(false)
    menuButtonRef.current?.focus()
  }

  async function handleLogout() {
    setMenuOpen(false)
    await logout()
    navigate('/login', { replace: true })
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-11 w-full items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-medium transition cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood ${
      isActive
        ? 'bg-blood text-white shadow-lg shadow-blood/20'
        : 'text-olive hover:bg-vanilla/40 hover:text-bean'
    }`

  const brand = (
      <div className="flex items-center gap-2.5">
      <img src="/clubsphere-logo.svg" alt="" className="h-9 w-9 shrink-0 rounded-xl" />
      <span className="font-serif text-xl font-bold tracking-tight text-bean">ClubSphere</span>
    </div>
  )

  return (
    <div className="workspace-shell flex min-h-dvh flex-col text-bean lg:flex-row">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex min-h-14 items-center justify-between border-b border-rose/30 bg-white/90 px-3 pt-[env(safe-area-inset-top)] backdrop-blur-xl lg:hidden">
        <div className="flex items-center gap-2">
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={menuOpen}
            aria-controls="app-sidebar"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-rose/30 text-bean transition hover:border-blood/40 hover:text-blood focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood cursor-pointer"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-5 w-5" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          {brand}
        </div>

        <div className="flex items-center gap-2">
          <NotificationsPopover isAuthenticated={isAuthenticated} />
        </div>
      </header>

      {/* Scrim: dims background content on mobile */}
      <div
        onClick={closeMenu}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-bean/60 backdrop-blur-sm transition-opacity duration-300 lg:hidden ${
          menuOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />

      {/* Sidebar / off-canvas drawer */}
      <aside
        id="app-sidebar"
        ref={sidebarRef}
        aria-label="Primary navigation"
        aria-modal={menuOpen ? 'true' : undefined}
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-rose/30 bg-[#fffdf8]/95 backdrop-blur-xl transition-[transform,visibility] duration-300 ease-out lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:w-64 lg:max-w-none lg:translate-x-0 lg:visible ${
          menuOpen ? 'visible translate-x-0' : 'invisible -translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b-2 border-bean/80 px-5 pt-[env(safe-area-inset-top)]">
          {brand}
          <button
            ref={closeButtonRef}
            type="button"
            onClick={closeMenu}
            aria-label="Close navigation menu"
            className="flex h-10 w-10 items-center justify-center rounded-xl text-olive transition hover:bg-vanilla/40 hover:text-bean focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood cursor-pointer lg:hidden"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-5 w-5" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.filter((item) => !('roles' in item) || (item.roles as readonly string[]).includes(user?.role ?? '')).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMenuOpen(false)}
              className={linkClass}
            >
              <SidebarIcon name={item.icon} />
              <span className="min-w-0 flex-1">{item.label}</span>
              {item.to === '/manage-club' && (
                <span
                  aria-label={`${pendingRequestCount} pending requests`}
                  className="inline-flex min-w-5 items-center justify-center border border-current/25 px-1.5 py-0.5 text-[10px] font-bold tabular-nums"
                >
                  {pendingRequestCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Profile and sign out footer */}
        <div className="border-t border-rose/30 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-vanilla text-xs font-bold text-bean">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-bean">{user?.full_name}</p>
                <p className="truncate text-xs text-olive">
                  {ROLE_LABELS[user?.role ?? ''] ?? user?.role}
                </p>
              </div>
            </div>
            <div className="hidden lg:block">
              <NotificationsPopover isAuthenticated={isAuthenticated} />
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="mt-3 min-h-11 w-full rounded-lg border border-rose/30 bg-white px-3 py-2 text-xs font-medium text-bean transition hover:border-blood/40 hover:text-blood focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood cursor-pointer"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Routed page content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <main className="workspace-main flex-1 overflow-x-hidden">
          <div className="workspace-content mx-auto w-full px-4 pb-10 sm:px-6 lg:px-10">
            <Outlet />
          </div>
        </main>
        <GazetteFooter />
      </div>
    </div>
  )
}
