import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { clubService } from '../services/clubService'
import { uploadService } from '../services/uploadService'
import type { Club, ClubAchievement, ClubCoreMember, ClubRecentEvent, MembershipMember } from '../domain/types'
import { EmptyState, ErrorNote, PageHeader, SkeletonGrid, StatusBadge } from '../components/ui'
import { formatDate } from '../lib/format'
import { useToast } from '../context/ToastContext'

type MembershipTab = 'requested' | 'active' | 'all' | 'profile'

export default function ManageClubPage() {
  const { user } = useAuth()
  const toast = useToast()
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
  const [actionBusyId, setActionBusyId] = useState<number | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [memberRoleDrafts, setMemberRoleDrafts] = useState<Record<number, string>>({})

  const [profileMotives, setProfileMotives] = useState('')
  const [profileDescription, setProfileDescription] = useState('')
  const [profileLogoUrl, setProfileLogoUrl] = useState<string | null>(null)
  const [profileCharterUrl, setProfileCharterUrl] = useState<string | null>(null)
  const [profileEvents, setProfileEvents] = useState<ClubRecentEvent[]>([])
  const [selectedEventPosterId, setSelectedEventPosterId] = useState<number | ''>('')
  const [uploadingMedia, setUploadingMedia] = useState<string | null>(null)
  const [profileContacts, setProfileContacts] = useState<ClubCoreMember[]>([])
  const [profileAchievements, setProfileAchievements] = useState<ClubAchievement[]>([])
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)

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
          : user?.role === 'Club Manager'
            ? allClubs.filter((c) => c.manager_user_id === user.user_id)
            : []

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
    setError(null)
  }

  // 2. Fetch membership records for the selected club & tab
  const fetchMembers = useCallback(async () => {
    if (!selectedClubId) {
      setMembers([])
      setPendingCount(0)
      return
    }

    setLoadingMembers(true)
    setError(null)

    try {
      const statusParam = activeTab === 'all' ? undefined : activeTab
      const [res, pending] = await Promise.all([
        clubService.getClubMembers(selectedClubId, statusParam, 1, 100),
        activeTab === 'requested'
          ? Promise.resolve(null)
          : clubService.getClubMembers(selectedClubId, 'requested', 1, 1),
      ])
      setMembers(res.items || [])
      setPendingCount(activeTab === 'requested' ? res.total : pending?.total ?? 0)
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

    try {
      await clubService.updateMembershipStatus(selectedClubId, member.membership_id, {
        status: newStatus,
        role: newStatus === 'active' ? role : undefined,
      })

      const statusChanged = member.status !== newStatus
      const actionLabel = newStatus === 'active'
        ? statusChanged ? 'Approved membership request for' : 'Updated role for'
        : member.status === 'requested' ? 'Rejected membership request for' : 'Removed from club'
      toast.success(`${actionLabel} ${member.full_name}.`)

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

      if (statusChanged && (newStatus === 'active' || member.status === 'active')) {
        const delta = newStatus === 'active' ? 1 : -1
        setClubs((prev) => prev.map((c) => c.club_id === selectedClubId
          ? { ...c, member_count: Math.max(0, (c.member_count ?? 0) + delta) }
          : c))
      }
      if (member.status === 'requested' && statusChanged) setPendingCount((count) => Math.max(0, count - 1))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : `Failed to update ${member.full_name}'s membership.`
      setError(message)
      toast.error(message)
    } finally {
      setActionBusyId(null)
    }
  }

  useEffect(() => {
    if (!selectedClubId || activeTab !== 'profile') return
    let cancelled = false
    setLoadingProfile(true)
    clubService
      .getClub(selectedClubId)
      .then((detail) => {
        if (cancelled) return
        setProfileMotives(detail.motives || '')
        setProfileDescription(detail.description || '')
        setProfileLogoUrl(detail.logo_url || null)
        setProfileCharterUrl(detail.charter_pdf_url || null)
        setProfileEvents(detail.recent_events || [])
        setSelectedEventPosterId(detail.recent_events?.[0]?.event_id ?? '')
        setProfileContacts(
          detail.core_members?.length
            ? detail.core_members
            : [
                { role: 'President', name: '', email: '', phone: '' },
                { role: 'Vice President', name: '', email: '', phone: '' },
                { role: 'Media Head', name: '', email: '', phone: '' },
                { role: 'Tech Head', name: '', email: '', phone: '' },
              ],
        )
        setProfileAchievements(detail.past_achievements || [])
      })
      .catch((err: unknown) => {
        if (cancelled) return
        toast.error(err instanceof Error ? err.message : 'Failed to load club details.')
      })
      .finally(() => {
        if (!cancelled) setLoadingProfile(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedClubId, activeTab, toast])

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedClubId) return
    setSavingProfile(true)
    try {
      await clubService.updateClub(selectedClubId, {
        motives: profileMotives,
        description: profileDescription,
        leadership_contacts: profileContacts.filter((c) => c.name.trim() && c.email.trim()),
        past_achievements: profileAchievements.filter((a) => a.title.trim() && a.description.trim()),
      })
      toast.success('Club motives, contacts, and achievements updated successfully!')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to update club profile.')
    } finally {
      setSavingProfile(false)
    }
  }

  const handleClubMediaUpload = async (file: File | undefined, kind: 'logo' | 'charter') => {
    if (!file || !selectedClubId) return
    setUploadingMedia(kind)
    try {
      const res = await uploadService.uploadFile(file, 'Clubs', selectedClubId, kind)
      const mediaUrl = res.blob_url || `/api/v1/uploads/media/${res.upload_id}`
      if (kind === 'logo') {
        setProfileLogoUrl(mediaUrl)
        setClubs((prev) => prev.map((c) => (c.club_id === selectedClubId ? { ...c, logo_url: mediaUrl } : c)))
      } else {
        setProfileCharterUrl(mediaUrl)
      }
      toast.success(kind === 'logo' ? 'Club logo uploaded cleanly!' : 'Official charter PDF uploaded!')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploadingMedia(null)
    }
  }

  const handleEventPosterUpload = async (file: File | undefined) => {
    if (!file || !selectedEventPosterId) return
    setUploadingMedia('poster')
    try {
      await uploadService.uploadFile(file, 'Events', Number(selectedEventPosterId), 'poster')
      toast.success('Event poster uploaded to Blob Storage!')
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Event poster upload failed.')
    } finally {
      setUploadingMedia(null)
    }
  }

  const selectedClub = clubs.find((c) => c.club_id === selectedClubId)
  const roleOptions = ['Member', 'Lead', 'Coordinator', 'Technical Lead', 'Secretary']

  return (
    <div>
      <PageHeader
        title="Club Management"
        icon="👥"
        subtitle="Review membership applications, approve prospective members, and manage your club roster."
      />

      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      {loadingClubs ? (
        <SkeletonGrid count={2} compact />
      ) : clubs.length === 0 ? (
        <div className="editorial-card p-8 text-center sm:p-12">
          <h2 className="text-xl font-bold text-bean">No clubs assigned to your account yet</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-olive">An administrator can assign a club to your account. Once assigned, its membership requests and roster will appear here.</p>
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
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'requested'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>Pending Requests</span>
                <span className="rounded-full bg-white/20 px-1.5 py-0.2 text-[10px]">{pendingCount}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveTab('active')
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
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'all'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>All History</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveTab('profile')
                }}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition cursor-pointer ${
                  activeTab === 'profile'
                    ? 'bg-blood text-white shadow-sm'
                    : 'text-olive hover:bg-vanilla/50 hover:text-bean'
                }`}
              >
                <span>Club Motives &amp; Laurels</span>
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

          {/* Active Tab Content */}
          {activeTab === 'profile' ? (
            loadingProfile ? (
              <SkeletonGrid count={2} compact />
            ) : (
              <form onSubmit={(e) => void handleSaveProfile(e)} className="editorial-card p-6 sm:p-8 space-y-6">
                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="font-serif text-lg font-bold text-bean">Club Motives, Vision &amp; Laurels</h2>
                    <span className="text-xs uppercase tracking-widest text-olive">Public Profile</span>
                  </div>
                  <p className="mt-1 text-xs text-olive">
                    These details appear on your public Club Details page (<code className="text-blood">/clubs/{selectedClubId}</code>) so interested students can learn about your mission, past trophies, and leadership.
                  </p>
                </div>

                <div className="space-y-4">
                  <div>
                    <label htmlFor="profile-motives" className="block text-xs font-bold uppercase tracking-wider text-bean mb-1">
                      Motives &amp; Mission Vision
                    </label>
                    <textarea
                      id="profile-motives"
                      rows={4}
                      value={profileMotives}
                      onChange={(e) => setProfileMotives(e.target.value)}
                      placeholder="Describe the club's core purpose, values, learning tracks, and member experience..."
                      className="editorial-field w-full px-3.5 py-2.5 text-sm"
                    />
                  </div>

                  <div>
                    <label htmlFor="profile-description" className="block text-xs font-bold uppercase tracking-wider text-bean mb-1">
                      Short Tagline / Overview
                    </label>
                    <textarea
                      id="profile-description"
                      rows={2}
                      value={profileDescription}
                      onChange={(e) => setProfileDescription(e.target.value)}
                      placeholder="Brief overview summarizing the club focus..."
                      className="editorial-field w-full px-3.5 py-2.5 text-sm"
                    />
                  </div>
                </div>

                {/* Azure Blob Storage Media & Documents */}
                <div className="border-t border-rose/30 pt-6">
                  <h3 className="font-serif text-base font-bold text-bean mb-1">Club Media &amp; Official Charter (Azure Blob Storage)</h3>
                  <p className="text-xs text-olive mb-4">
                    Upload your club crest logo, official charter PDF, or event posters. Files are persisted via Azure Blob Storage and rendered on public cards.
                  </p>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <div className="rounded-xl border border-rose/30 bg-vanilla/30 p-4 space-y-2.5">
                      <span className="block text-[11px] font-bold uppercase tracking-wider text-bean">Club Logo (PNG/JPG/WebP)</span>
                      {profileLogoUrl && (
                        <img
                          src={profileLogoUrl}
                          alt="Current club logo"
                          className="h-16 w-16 rounded-lg border border-rose/30 bg-white object-cover"
                        />
                      )}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        disabled={uploadingMedia !== null}
                        onChange={(e) => void handleClubMediaUpload(e.target.files?.[0], 'logo')}
                        className="block w-full text-xs text-olive file:mr-2 file:rounded-lg file:border-0 file:bg-blood file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-bean"
                      />
                      {uploadingMedia === 'logo' && <p className="text-[11px] text-blood">Uploading logo…</p>}
                    </div>

                    <div className="rounded-xl border border-rose/30 bg-vanilla/30 p-4 space-y-2.5">
                      <span className="block text-[11px] font-bold uppercase tracking-wider text-bean">Charter Document (PDF)</span>
                      {profileCharterUrl && (
                        <a
                          href={profileCharterUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block text-xs font-semibold text-blood underline"
                        >
                          Current Charter PDF ↗
                        </a>
                      )}
                      <input
                        type="file"
                        accept="application/pdf"
                        disabled={uploadingMedia !== null}
                        onChange={(e) => void handleClubMediaUpload(e.target.files?.[0], 'charter')}
                        className="block w-full text-xs text-olive file:mr-2 file:rounded-lg file:border-0 file:bg-blood file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-bean"
                      />
                      {uploadingMedia === 'charter' && <p className="text-[11px] text-blood">Uploading PDF…</p>}
                    </div>

                    <div className="rounded-xl border border-rose/30 bg-vanilla/30 p-4 space-y-2.5">
                      <span className="block text-[11px] font-bold uppercase tracking-wider text-bean">Event Poster (PNG/JPG/WebP)</span>
                      {profileEvents.length > 0 ? (
                        <>
                          <select
                            value={selectedEventPosterId}
                            onChange={(e) => setSelectedEventPosterId(e.target.value ? Number(e.target.value) : '')}
                            className="editorial-field w-full px-2.5 py-1.5 text-xs"
                          >
                            {profileEvents.map((ev) => (
                              <option key={ev.event_id} value={ev.event_id}>
                                {ev.title}
                              </option>
                            ))}
                          </select>
                          <input
                            type="file"
                            accept="image/png,image/jpeg,image/webp"
                            disabled={uploadingMedia !== null || !selectedEventPosterId}
                            onChange={(e) => void handleEventPosterUpload(e.target.files?.[0])}
                            className="block w-full text-xs text-olive file:mr-2 file:rounded-lg file:border-0 file:bg-blood file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-bean"
                          />
                          {uploadingMedia === 'poster' && <p className="text-[11px] text-blood">Uploading poster…</p>}
                        </>
                      ) : (
                        <p className="text-xs italic text-olive">No events created for this club yet.</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Core Leadership Contacts */}
                <div className="border-t border-rose/30 pt-6">
                  <h3 className="font-serif text-base font-bold text-bean mb-1">Core Leadership Team</h3>
                  <p className="text-xs text-olive mb-4">
                    List your primary leads and domain heads (President, Vice President, Media Head, Tech Head) for peer contacts.
                  </p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {profileContacts.map((contact, idx) => (
                      <div key={idx} className="rounded-xl border border-rose/30 bg-vanilla/40 p-4 space-y-2.5">
                        <span className="inline-block rounded bg-blood/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blood">
                          {contact.role}
                        </span>
                        <div>
                          <label className="block text-[11px] font-semibold text-olive">Name</label>
                          <input
                            type="text"
                            value={contact.name}
                            onChange={(e) => {
                              const val = e.target.value
                              setProfileContacts((prev) => prev.map((c, i) => i === idx ? { ...c, name: val } : c))
                            }}
                            placeholder="Full name"
                            className="editorial-field w-full px-2.5 py-1.5 text-xs"
                          />
                        </div>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          <div>
                            <label className="block text-[11px] font-semibold text-olive">Email</label>
                            <input
                              type="email"
                              value={contact.email}
                              onChange={(e) => {
                                const val = e.target.value
                                setProfileContacts((prev) => prev.map((c, i) => i === idx ? { ...c, email: val } : c))
                              }}
                              placeholder="lead@university.edu"
                              className="editorial-field w-full px-2.5 py-1.5 text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-semibold text-olive">Phone</label>
                            <input
                              type="text"
                              value={contact.phone || ''}
                              onChange={(e) => {
                                const val = e.target.value
                                setProfileContacts((prev) => prev.map((c, i) => i === idx ? { ...c, phone: val } : c))
                              }}
                              placeholder="+91 98765 43210"
                              className="editorial-field w-full px-2.5 py-1.5 text-xs"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Achievements */}
                <div className="border-t border-rose/30 pt-6">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="font-serif text-base font-bold text-bean">Past Achievements &amp; Laurels</h3>
                      <p className="text-xs text-olive">Major hackathon wins, summit awards, or milestone accomplishments.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setProfileAchievements((prev) => [
                          ...prev,
                          { title: '', date: '', award_or_highlight: '', description: '' },
                        ])
                      }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-blood/30 bg-blood/5 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-blood transition hover:bg-blood hover:text-white cursor-pointer"
                    >
                      + Add Laurels
                    </button>
                  </div>

                  {profileAchievements.length === 0 ? (
                    <p className="text-xs italic text-olive">No achievements listed yet. Click "+ Add Laurels" above.</p>
                  ) : (
                    <div className="space-y-3">
                      {profileAchievements.map((ach, idx) => (
                        <div key={idx} className="rounded-xl border border-rose/30 bg-white p-4 space-y-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-bold text-blood">Achievement #{idx + 1}</span>
                            <button
                              type="button"
                              onClick={() => {
                                setProfileAchievements((prev) => prev.filter((_, i) => i !== idx))
                              }}
                              className="text-xs font-semibold text-blood/70 hover:text-blood cursor-pointer"
                            >
                              ✕ Remove
                            </button>
                          </div>
                          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                            <div className="sm:col-span-2">
                              <label className="block text-[11px] font-semibold text-olive">Title</label>
                              <input
                                type="text"
                                value={ach.title}
                                onChange={(e) => {
                                  const val = e.target.value
                                  setProfileAchievements((prev) => prev.map((a, i) => i === idx ? { ...a, title: val } : a))
                                }}
                                placeholder="e.g., 1st Place - Smart India Hackathon"
                                className="editorial-field w-full px-2.5 py-1.5 text-xs"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-olive">Date / Period</label>
                              <input
                                type="text"
                                value={ach.date || ''}
                                onChange={(e) => {
                                  const val = e.target.value
                                  setProfileAchievements((prev) => prev.map((a, i) => i === idx ? { ...a, date: val } : a))
                                }}
                                placeholder="e.g., Oct 2026"
                                className="editorial-field w-full px-2.5 py-1.5 text-xs"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="block text-[11px] font-semibold text-olive">Award or Highlight Badge</label>
                            <input
                              type="text"
                              value={ach.award_or_highlight || ''}
                              onChange={(e) => {
                                const val = e.target.value
                                setProfileAchievements((prev) => prev.map((a, i) => i === idx ? { ...a, award_or_highlight: val } : a))
                              }}
                              placeholder="e.g., Gold Medalist & ₹1,00,000 Cash Prize"
                              className="editorial-field w-full px-2.5 py-1.5 text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-semibold text-olive">Description</label>
                            <textarea
                              rows={2}
                              value={ach.description}
                              onChange={(e) => {
                                const val = e.target.value
                                setProfileAchievements((prev) => prev.map((a, i) => i === idx ? { ...a, description: val } : a))
                              }}
                              placeholder="Brief summary of what the team built or presented..."
                              className="editorial-field w-full px-2.5 py-1.5 text-xs"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-end gap-3 pt-4 border-t border-rose/30">
                  <button
                    type="submit"
                    disabled={savingProfile}
                    className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blood px-6 py-2.5 text-xs font-bold uppercase tracking-widest text-white shadow-sm transition hover:bg-blood/90 cursor-pointer disabled:opacity-50"
                  >
                    {savingProfile ? (
                      <>
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                        Saving Profile...
                      </>
                    ) : (
                      'Save Club Details'
                    )}
                  </button>
                </div>
              </form>
            )
          ) : (
            <>
              {/* Members / Requests List */}
              {loadingMembers ? (
                <SkeletonGrid count={3} compact />
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
                            <div className="flex flex-wrap items-center gap-2">
                              <label className="sr-only" htmlFor={`member-role-${member.membership_id}`}>Role for {member.full_name}</label>
                              <select
                                id={`member-role-${member.membership_id}`}
                                value={memberRoleDrafts[member.membership_id] ?? member.role}
                                onChange={(event) => setMemberRoleDrafts((prev) => ({ ...prev, [member.membership_id]: event.target.value }))}
                                className="editorial-field min-h-9 px-2 py-1 text-xs"
                              >
                                {roleOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                              </select>
                              <button
                                type="button"
                                disabled={isBusy || (memberRoleDrafts[member.membership_id] ?? member.role) === member.role}
                                onClick={() => void handleUpdateStatus(member, 'active', memberRoleDrafts[member.membership_id] ?? member.role)}
                                className="inline-flex min-h-9 items-center gap-1.5 border border-blood/30 bg-white px-3 py-1.5 text-xs font-bold uppercase text-blood hover:bg-blood hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                              >Save role</button>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void handleUpdateStatus(member, 'removed')}
                                className="inline-flex min-h-9 items-center gap-1.5 border border-rose/30 bg-white px-3 py-1.5 text-xs font-medium text-olive transition hover:border-blood/30 hover:bg-blood/5 hover:text-blood disabled:opacity-50 cursor-pointer"
                                title="Remove from club roster"
                              >Remove</button>
                            </div>
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
        </>
      )}
    </div>
  )
}
