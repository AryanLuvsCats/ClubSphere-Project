import { useCallback, useEffect, useState } from 'react'
import { clubService } from '../services/clubService'
import type { Club } from '../domain/types'
import { useToast } from '../context/ToastContext'

export type JoinState = { kind: 'success' | 'error'; message: string } | null

export function useJoinClub(initialClubId?: string | null) {
  const [clubs, setClubs] = useState<Club[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyClubId, setBusyClubId] = useState<number | null>(null)
  const [joinState, setJoinState] = useState<Record<number, JoinState>>({})
  const [membershipStatusByClub, setMembershipStatusByClub] = useState<Record<number, string>>({})
  const toast = useToast()

  const loadClubs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [res, memberships] = await Promise.all([
        clubService.getClubs({ search, status: 'active', page_size: 50 }),
        clubService.getMyMembershipStatuses(),
      ])
      setClubs(res.items)
      setMembershipStatusByClub(Object.fromEntries(memberships.map((item) => [item.club_id, item.status])))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load active clubs.')
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadClubs(), 300)
    return () => window.clearTimeout(timer)
  }, [loadClubs])

  const requestToJoin = useCallback(async (club: Club) => {
    setBusyClubId(club.club_id)
    setJoinState((prev) => ({ ...prev, [club.club_id]: null }))
    try {
      await clubService.requestJoinClub(club.club_id)
      setMembershipStatusByClub((prev) => ({ ...prev, [club.club_id]: 'requested' }))
      toast.success(`Membership request sent to ${club.name}.`)
      setJoinState((prev) => ({
        ...prev,
        [club.club_id]: {
          kind: 'success',
          message: 'Request sent — the club manager will review your application.',
        },
      }))
    } catch (err) {
      setJoinState((prev) => ({
        ...prev,
        [club.club_id]: {
          kind: 'error',
          message: err instanceof Error ? err.message : 'Could not submit your request.',
        },
      }))
      toast.error(err instanceof Error ? err.message : 'Could not submit your request.')
    } finally {
      setBusyClubId(null)
    }
  }, [toast])

  return {
    clubs,
    search,
    setSearch,
    loading,
    error,
    busyClubId,
    joinState,
    membershipStatusByClub,
    requestToJoin,
    initialClubId,
  }
}
