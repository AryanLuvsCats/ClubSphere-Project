import { formatDate } from '../../lib/format'
import { ErrorNote, StatusBadge } from '../ui'
import type { Proposal } from '../../domain/types'
import type { ReviewDecision } from '../../services/proposalService'

interface ProposalCardProps {
  proposal: Proposal
  canReview: boolean
  isFaculty: boolean
  reviewing: boolean
  reviewError?: string | null
  comment: string
  onCommentChange: (value: string) => void
  onReview: (decision: ReviewDecision) => void
}

export function ProposalCard({
  proposal,
  canReview,
  isFaculty,
  reviewing,
  reviewError,
  comment,
  onCommentChange,
  onReview,
}: ProposalCardProps) {
  const actionable = canReview && (proposal.status === 'submitted' || proposal.status === 'changes_requested')

  return (
    <article className="editorial-card p-5 sm:p-6">
      <div className="mb-3 flex items-center justify-between border-b border-rose/25 pb-2">
        <span className="editorial-label">Charter proposal / {String(proposal.proposal_id).padStart(3, '0')}</span>
        <StatusBadge status={proposal.status} />
      </div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-2xl font-semibold text-bean">{proposal.proposed_name}</h3>
          <p className="mt-0.5 text-xs text-olive">
            by <span className="font-medium text-bean">{proposal.applicant_name ?? 'Unknown applicant'}</span>
            {' • '}
            {proposal.program_name ?? 'Unknown program'}
            {proposal.branch_name && ` (${proposal.branch_name})`}
          </p>
        </div>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-olive">{proposal.description}</p>
      <p className="mt-2 text-[11px] text-olive">Submitted {formatDate(proposal.submitted_at)}</p>

      {proposal.approvals.length > 0 ? (
        <ol className="mt-4 space-y-2 border-t border-rose/30 pt-4">
          {proposal.approvals.map((approval) => (
            <li key={approval.approval_id} className="text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold uppercase tracking-wide text-bean">{approval.stage}</span>
                <StatusBadge status={approval.decision === 'approve' ? 'approved' : approval.decision} />
                <span className="text-olive">
                  by {approval.reviewer_name ?? 'Reviewer'} on {formatDate(approval.decided_at)}
                </span>
              </div>
              {approval.comment && (
                <p className="mt-1 rounded-lg bg-vanilla/30 px-3 py-2 text-olive">“{approval.comment}”</p>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-4 border-t border-rose/30 pt-4 text-xs text-olive">
          Awaiting first review by a Faculty Advisor.
        </p>
      )}

      {actionable && (
        <div className="mt-4 border-t border-rose/30 pt-4">
          <label
            htmlFor={`review-comment-${proposal.proposal_id}`}
            className="mb-1.5 block text-xs font-medium text-olive"
          >
            Reviewer comment <span className="text-rose font-normal">(required to reject or request changes)</span>
          </label>
          <textarea
            id={`review-comment-${proposal.proposal_id}`}
            rows={2}
            value={comment}
            onChange={(e) => onCommentChange(e.target.value)}
            placeholder="Add your reasoning for the applicant…"
            className="w-full resize-y rounded-xl border border-rose/30 bg-white px-3 py-2 text-xs text-bean placeholder-rose outline-none transition focus:border-blood focus:ring-2 focus:ring-blood/20"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={reviewing}
              onClick={() => onReview('approve')}
              className="editorial-button bg-olive px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-bean disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
            >
              {reviewing
                ? 'Recording…'
                : isFaculty
                  ? 'Recommend approval'
                  : 'Approve & charter club'}
            </button>
            <button
              type="button"
              disabled={reviewing}
              onClick={() => onReview('changes_requested')}
              className="editorial-button border border-rose/40 bg-rose/10 px-3.5 py-2 text-xs font-semibold text-bean transition hover:bg-rose/20 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
            >
              Request changes
            </button>
            <button
              type="button"
              disabled={reviewing}
              onClick={() => onReview('reject')}
              className="editorial-button border border-blood/40 bg-blood/10 px-3.5 py-2 text-xs font-semibold text-blood transition hover:bg-blood/20 disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer"
            >
              Reject
            </button>
          </div>
          {reviewError && (
            <div className="mt-3">
              <ErrorNote message={reviewError} />
            </div>
          )}
        </div>
      )}
    </article>
  )
}
