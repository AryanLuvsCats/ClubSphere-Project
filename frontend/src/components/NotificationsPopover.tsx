import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useNotifications } from '../hooks/useNotifications'
import { formatDate } from '../lib/format'

export default function NotificationsPopover({ isAuthenticated }: { isAuthenticated: boolean }) {
  const navigate = useNavigate()
  const { notifications, unreadCount, markAsRead, markAllAsRead, loading, error, refreshNotifications } = useNotifications(isAuthenticated)
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const popoverRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const updatePosition = useCallback(() => {
    const rect = buttonRef.current?.getBoundingClientRect()
    if (!rect) return
    const panelWidth = Math.min(384, window.innerWidth - 32)
    const panelHeight = Math.min(430, window.innerHeight - 32)
    const left = rect.right + 12 + panelWidth <= window.innerWidth - 16
      ? rect.right + 12
      : Math.max(16, Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - 16))
    const top = rect.bottom + 12 + panelHeight <= window.innerHeight - 16
      ? rect.bottom + 12
      : Math.max(16, rect.top - panelHeight - 12)
    setPosition({ top, left })
  }, [])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      updatePosition()
      window.addEventListener('resize', updatePosition)
      window.addEventListener('scroll', updatePosition, true)
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        window.removeEventListener('resize', updatePosition)
        window.removeEventListener('scroll', updatePosition, true)
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [open, updatePosition])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && open) {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  if (!isAuthenticated) return null

  return (
    <div className="relative" ref={popoverRef}>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          const nextOpen = !open
          setOpen(nextOpen)
          if (nextOpen) void refreshNotifications()
        }}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-rose/30 bg-white text-olive transition hover:border-blood/40 hover:text-bean focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blood cursor-pointer"
      >
        {/* Bell Icon */}
        <svg
          className="h-5 w-5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>

        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-blood px-1 text-[10px] font-bold text-white shadow-sm">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          style={{ top: position.top, left: position.left }}
          className="notification-panel fixed z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col rounded-sm border border-rose/30 bg-white p-4 shadow-xl sm:w-96"
        >
          <div className="flex items-center justify-between border-b border-rose/30 pb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-bean">Notifications</h3>
              {unreadCount > 0 && (
                <span className="rounded-full bg-blood/10 px-2 py-0.5 text-[11px] font-semibold text-blood">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void markAllAsRead()}
                className="text-xs font-medium text-blood hover:underline cursor-pointer"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="mt-3 max-h-[min(20rem,calc(100dvh-10rem))] space-y-2.5 overflow-y-auto pr-1">
            {loading && notifications.length === 0 ? (
              <p className="py-6 text-center text-xs text-olive">Loading notifications…</p>
            ) : error && notifications.length === 0 ? (
              <p role="alert" className="py-6 text-center text-xs text-blood">Notifications couldn’t be loaded. Try opening this panel again.</p>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-xs font-semibold text-bean">No notifications yet</p>
                <p className="mt-1 text-[11px] text-olive">Activity on your clubs and events will appear here.</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.notification_id}
                  onClick={() => {
                    if (!n.is_read) void markAsRead(n.notification_id)
                    if (n.type === 'MEMBERSHIP_REQUEST') {
                      setOpen(false)
                      navigate('/manage-club')
                    }
                  }}
                  className={`flex flex-col gap-1 rounded-xl p-3 text-xs transition cursor-pointer ${
                    n.is_read
                      ? 'bg-white hover:bg-vanilla/30'
                      : 'border border-blood/20 bg-blood/5 font-medium'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[10px] uppercase tracking-wider text-blood font-bold">
                      {n.type.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[10px] text-olive shrink-0">{formatDate(n.created_at)}</span>
                  </div>
                  <p className="text-bean leading-relaxed">{n.message}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
