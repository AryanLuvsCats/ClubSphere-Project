import { useEffect, useState } from 'react'
import { clubService } from '../services/clubService'
import type { SessionProfile } from '../domain/types'

export function usePendingMembershipCount(user: SessionProfile | null) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (!user || !['Club Manager', 'Administrator'].includes(user.role)) {
      setCount(0)
      return
    }

    let cancelled = false
    const refresh = () => {
      clubService.getPendingRequestCount()
        .then((result) => {
          if (!cancelled) setCount(result.count)
        })
        .catch(() => {
          if (!cancelled) setCount(0)
        })
    }

    refresh()
    const interval = window.setInterval(refresh, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [user?.user_id, user?.role])

  return count
}
