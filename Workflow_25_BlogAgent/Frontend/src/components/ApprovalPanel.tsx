import { useState } from 'react'
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { approveBlog, rejectBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  blog: Blog
  onDecision: (updatedBlog: Partial<Blog>) => void
}

export default function ApprovalPanel({ blog, onDecision }: Props) {
  const [rejecting, setRejecting]   = useState(false)
  const [reason, setReason]         = useState('')
  const [loadingApp, setLoadingApp] = useState(false)
  const [loadingRej, setLoadingRej] = useState(false)

  async function handleApprove() {
    setLoadingApp(true)
    try {
      await approveBlog(blog.thread_id)
      toast.success('Blog approved! Generating images…')
      onDecision({ status: 'APPROVED' })
    } catch (err: any) {
      toast.error(err.message || 'Approval failed')
    } finally {
      setLoadingApp(false)
    }
  }

  async function handleReject() {
    if (!reason.trim()) { toast.error('Please provide a rejection reason'); return }
    setLoadingRej(true)
    try {
      await rejectBlog(blog.thread_id, reason.trim())
      toast.success('Blog rejected.')
      onDecision({ status: 'REJECTED', rejection_reason: reason.trim() })
      setRejecting(false)
      setReason('')
    } catch (err: any) {
      toast.error(err.message || 'Rejection failed')
    } finally {
      setLoadingRej(false)
    }
  }

  if (blog.status !== 'PENDING') return null

  return (
    <div style={{
      background: 'rgba(251,191,36,0.05)',
      border: '1px solid rgba(251,191,36,0.2)',
      borderRadius: 12,
      padding: '16px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <AlertCircle size={16} color="#fbbf24" />
        <span style={{ fontWeight: 600, color: '#fbbf24', fontSize: 14 }}>
          Awaiting Your Review
        </span>
      </div>
      <p style={{ fontSize: 13, color: '#9fb3c8', margin: '0 0 14px' }}>
        Read the generated blog content above, then approve to publish or reject with a reason.
      </p>

      {!rejecting ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-green"
            onClick={handleApprove}
            disabled={loadingApp}
          >
            {loadingApp
              ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Approving…</>
              : <><CheckCircle size={14} /> Approve & Publish</>
            }
          </button>
          <button
            className="btn btn-red"
            onClick={() => setRejecting(true)}
          >
            <XCircle size={14} /> Reject
          </button>
        </div>
      ) : (
        <div>
          <textarea
            className="input"
            rows={3}
            placeholder="Reason for rejection (required)…"
            value={reason}
            onChange={e => setReason(e.target.value)}
            style={{ resize: 'none', marginBottom: 10 }}
            autoFocus
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-red"
              onClick={handleReject}
              disabled={loadingRej || !reason.trim()}
            >
              {loadingRej
                ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Rejecting…</>
                : <><XCircle size={14} /> Confirm Rejection</>
              }
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setRejecting(false); setReason('') }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
