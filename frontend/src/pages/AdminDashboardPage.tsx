import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useAdminDashboard } from '../hooks/useAdminDashboard'
import { adminService } from '../services/adminService'
import { formatDate } from '../lib/format'
import { PROPOSAL_STATUS_TABS } from '../domain/constants'
import { isFacultyReviewer } from '../domain/permissions'
import type { AnalyticsExportResult } from '../domain/types'
import {
  EmptyState,
  ErrorNote,
  PageHeader,
  Spinner,
  SuccessNote,
} from '../components/ui'
import { StatCard } from '../components/admin/StatCard'
import { ProposalCard } from '../components/admin/ProposalCard'

export default function AdminDashboardPage() {
  const { user } = useAuth()
  const {
    allowedAnalytics,
    allowedAudit,
    allowedReview,
    overview,
    analyticsError,
    loadingAnalytics,
    auditLogs,
    auditError,
    loadingAudit,
    proposals,
    proposalsTotal,
    proposalsError,
    loadingProposals,
    statusFilter,
    setStatusFilter,
    reviewingId,
    reviewErrors,
    reviewSuccess,
    comments,
    setComment,
    handleReview,
  } = useAdminDashboard(user)

  const [exportingSnapshot, setExportingSnapshot] = useState(false)
  const [exportResult, setExportResult] = useState<AnalyticsExportResult | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  if (!allowedReview) {
    return (
      <div>
        <PageHeader title="Admin Dashboard" icon="🛡️" subtitle="Institution-wide governance and analytics." />
        <EmptyState
          title="Privileged access required"
          hint={`You are signed in as ${user?.role || 'an unprivileged user'}. Contact an administrator if you believe this is wrong.`}
        />
      </div>
    )
  }

  const attendanceRate = overview ? Math.round(overview.avg_attendance_rate * 100) : 0
  const isFaculty = isFacultyReviewer(user)

  const handleExportSnapshot = async () => {
    setExportingSnapshot(true)
    setExportError(null)
    try {
      const result = await adminService.exportAnalyticsSnapshot()
      setExportResult(result)
    } catch (err: unknown) {
      setExportError(err instanceof Error ? err.message : 'Failed to export analytics snapshot.')
    } finally {
      setExportingSnapshot(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Admin Dashboard"
        icon="🛡️"
        subtitle={
          allowedAnalytics
            ? 'Institution-wide governance and analytics, calculated live from database records.'
            : 'Department club proposal review and governance.'
        }
      />

      {allowedAnalytics && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-olive">
              Backed by Azure SQL Database (<code className="text-blood">vw_club_analytics_summary</code>) &amp; Azure Blob JSON snapshots.
            </p>
            <button
              type="button"
              onClick={() => void handleExportSnapshot()}
              disabled={exportingSnapshot || loadingAnalytics}
              className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-blood/40 bg-white px-4 py-2 text-xs font-bold uppercase tracking-wider text-blood transition hover:bg-blood hover:text-white disabled:opacity-50 cursor-pointer"
            >
              {exportingSnapshot ? 'Exporting JSON…' : 'Export JSON to Blob Storage ↗'}
            </button>
          </div>
          {exportError && <div className="mb-4"><ErrorNote message={exportError} /></div>}
          {exportResult && (
            <div className="mb-4">
              <SuccessNote
                message={`Snapshot saved (${exportResult.storage_backend}) -> container "${exportResult.container}" at "${exportResult.blob_path}" (${exportResult.size_bytes} bytes).`}
              />
            </div>
          )}
          {loadingAnalytics && <Spinner label="Loading analytics" />}
          {analyticsError && <ErrorNote message={analyticsError} />}

          {overview && !loadingAnalytics && (
            <>
              {/* Headline metrics */}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <StatCard
                  label="Active clubs"
                  value={overview.active_clubs}
                  hint={`${overview.total_clubs} chartered in total`}
                  accent="text-blood"
                />
                <StatCard
                  label="Pending proposals"
                  value={overview.pending_proposals}
                  hint="Awaiting Faculty or HOD review"
                  accent={overview.pending_proposals > 0 ? 'text-rose' : 'text-bean'}
                />
                <StatCard
                  label="Published events"
                  value={overview.published_events}
                  hint={`${overview.total_events} events on record`}
                  accent="text-olive"
                />
                <StatCard
                  label="Students"
                  value={overview.total_students}
                  hint="Registered student accounts"
                  accent="text-blood"
                />
              </div>

              {/* Secondary metrics */}
              <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard
                  label="Confirmed registrations"
                  value={overview.confirmed_registrations}
                  hint={`${overview.total_registrations} total registration attempts`}
                  accent="text-bean"
                />
                <StatCard
                  label="Attendance recorded"
                  value={overview.total_attendance}
                  hint="Verified attendance marks"
                  accent="text-bean"
                />
                <StatCard
                  label="Avg attendance rate"
                  value={`${attendanceRate}%`}
                  hint="Attendance ÷ confirmed registrations"
                  accent={attendanceRate >= 60 ? 'text-olive' : 'text-rose'}
                />
              </div>
            </>
          )}
        </>
      )}

      {/* Club applications — proposal review pipeline */}
      <section className={allowedAnalytics ? 'mt-10' : 'mt-2'}>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="editorial-label">The review desk</p>
            <h2 className="mt-1 text-3xl font-semibold text-bean">Club applications</h2>
            <p className="mt-1 text-xs text-olive">
              Proposals to charter new student clubs.
              {isFaculty
                ? ' As a Faculty Advisor, your recommendation advances the application to the Head of Department.'
                : ' Final approval charters the club immediately and appoints the applicant as Lead.'}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {PROPOSAL_STATUS_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setStatusFilter(tab.key)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition cursor-pointer ${
                  statusFilter === tab.key
                    ? 'bg-blood text-white shadow-sm'
                    : 'border border-rose/30 bg-white/75 text-olive hover:border-blood/40 hover:text-bean'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {reviewSuccess && (
          <div className="mt-4">
            <SuccessNote message={reviewSuccess} />
          </div>
        )}
        {proposalsError && (
          <div className="mt-4">
            <ErrorNote message={proposalsError} />
          </div>
        )}
        {loadingProposals && (
          <div className="mt-4">
            <Spinner label="Loading applications" />
          </div>
        )}

        {!loadingProposals && !proposalsError && proposals.length === 0 && (
          <div className="mt-4">
            <EmptyState
              title={statusFilter ? 'No applications with this status' : 'No club applications yet'}
              hint={
                statusFilter
                  ? 'Try a different filter to see other applications.'
                  : 'Applications submitted through “Apply for club” will appear here.'
              }
            />
          </div>
        )}

        {!loadingProposals && proposals.length > 0 && (
          <p className="mt-4 text-[11px] uppercase tracking-wider text-olive font-medium">
            Showing {proposals.length} of {proposalsTotal} application{proposalsTotal === 1 ? '' : 's'}
          </p>
        )}

        <div className="mt-3 space-y-4">
          {proposals.map((proposal) => (
            <ProposalCard
              key={proposal.proposal_id}
              proposal={proposal}
              canReview={allowedReview}
              isFaculty={isFaculty}
              reviewing={reviewingId === proposal.proposal_id}
              reviewError={reviewErrors[proposal.proposal_id]}
              comment={comments[proposal.proposal_id] ?? ''}
              onCommentChange={(value) => setComment(proposal.proposal_id, value)}
              onReview={(decision) => void handleReview(proposal, decision)}
            />
          ))}
        </div>
      </section>

      {/* Branch breakdown */}
      {allowedAnalytics && overview && !loadingAnalytics && (
        <section className="mt-10">
          <p className="editorial-label">Institutional view</p>
          <h2 className="mt-1 text-3xl font-semibold text-bean">Branch breakdown</h2>
          <p className="mt-1 text-xs text-olive">
            Club, event, and registration activity grouped by master branch (e.g. B.Tech, M.Tech).
          </p>

          {overview.branch_metrics.length === 0 ? (
            <div className="mt-4">
              <EmptyState title="No branches recorded" />
            </div>
          ) : (
            <div className="editorial-table mt-4 overflow-x-auto border border-rose/30 shadow-sm">
              <table className="w-full text-left text-sm">
                <thead className="bg-vanilla/20 text-xs uppercase tracking-wider text-olive">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Branch</th>
                    <th className="px-4 py-3 font-semibold">Active clubs</th>
                    <th className="px-4 py-3 font-semibold">Events hosted</th>
                    <th className="px-4 py-3 font-semibold">Registrations</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rose/20">
                  {overview.branch_metrics.map((branch) => (
                    <tr key={branch.branch_id} className="bg-white hover:bg-vanilla/10 transition">
                      <td className="px-4 py-3 font-medium text-bean">{branch.branch_name}</td>
                      <td className="px-4 py-3 text-bean">{branch.active_clubs}</td>
                      <td className="px-4 py-3 text-bean">{branch.events_hosted}</td>
                      <td className="px-4 py-3 text-bean">{branch.total_registrations}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {overview.club_summaries && overview.club_summaries.length > 0 && (
            <div className="mt-8">
              <p className="editorial-label">Power BI reporting view (vw_club_analytics_summary)</p>
              <h3 className="mt-1 text-2xl font-semibold text-bean">Club activity breakdown</h3>
              <div className="editorial-table mt-3 overflow-x-auto border border-rose/30 shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-vanilla/20 text-xs uppercase tracking-wider text-olive">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Club</th>
                      <th className="px-4 py-3 font-semibold">Branch</th>
                      <th className="px-4 py-3 font-semibold">Active Members</th>
                      <th className="px-4 py-3 font-semibold">Pending Requests</th>
                      <th className="px-4 py-3 font-semibold">Leaders</th>
                      <th className="px-4 py-3 font-semibold">Events</th>
                      <th className="px-4 py-3 font-semibold">Registrations</th>
                      <th className="px-4 py-3 font-semibold">Attendance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rose/20">
                    {overview.club_summaries.map((club) => (
                      <tr key={club.club_id} className="bg-white hover:bg-vanilla/10 transition">
                        <td className="px-4 py-3 font-medium text-bean">{club.club_name}</td>
                        <td className="px-4 py-3 text-olive">{club.branch_name}</td>
                        <td className="px-4 py-3 text-bean">{club.active_members}</td>
                        <td className="px-4 py-3 text-bean">{club.pending_members}</td>
                        <td className="px-4 py-3 text-bean">{club.leadership_count ?? 0}</td>
                        <td className="px-4 py-3 text-bean">{club.total_events}</td>
                        <td className="px-4 py-3 text-bean">{club.confirmed_registrations}</td>
                        <td className="px-4 py-3 text-bean">{club.total_attendance}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Audit trail — Administrator only */}
      {allowedAudit && (
        <section className="mt-10">
          <p className="editorial-label">The record</p>
          <h2 className="mt-1 text-3xl font-semibold text-bean">Recent audit activity</h2>
          <p className="mt-1 text-xs text-olive">
            Immutable record of sensitive operations — the last 25 entries.
          </p>

          <div className="mt-4 space-y-2">
            {loadingAudit && <Spinner label="Loading audit logs" />}
            {auditError && <ErrorNote message={auditError} />}
            {!loadingAudit && !auditError && auditLogs.length === 0 && (
              <EmptyState title="No audit entries yet" hint="Sensitive operations will appear here." />
            )}

            {auditLogs.map((log) => (
              <div
                key={log.audit_log_id}
                className="editorial-card rounded-none px-4 py-3 shadow-none"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-blood/10 px-2 py-0.5 font-mono text-[11px] font-semibold text-blood">
                      {log.action}
                    </span>
                    <span className="text-xs text-olive">
                      {log.entity_type} #{log.entity_id}
                    </span>
                  </div>
                  <span className="text-xs text-olive">{formatDate(log.created_at)}</span>
                </div>
                <p className="mt-1.5 text-xs text-olive">
                  by <span className="font-medium text-bean">{log.actor_name ?? 'Unknown'}</span>
                  {log.actor_email && <span className="text-olive"> ({log.actor_email})</span>}
                </p>
                {log.details && (
                  <pre className="mt-2 overflow-x-auto rounded-lg bg-vanilla/20 px-3 py-2 text-[11px] leading-relaxed text-bean">
                    {log.details}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
