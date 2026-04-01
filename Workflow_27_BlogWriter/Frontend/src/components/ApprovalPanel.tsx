import { useState } from 'react'
import { CheckCircle, XCircle, Eye } from 'lucide-react'
import toast from 'react-hot-toast'
import { approveBlog, rejectBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  blog: Blog
  onDecision: (updated: Partial<Blog>) => void
}

export default function ApprovalPanel({ blog, onDecision }: Props) {
  const [rejecting,   setRejecting]   = useState(false)
  const [reason,      setReason]      = useState('')
  const [loadingApp,  setLoadingApp]  = useState(false)
  const [loadingRej,  setLoadingRej]  = useState(false)

  if (blog.status !== 'PENDING') return null

  async function handleApprove() {
    setLoadingApp(true)
    try {
      await approveBlog(blog.thread_id)
      toast.success('Blog approved and published! 🎉')
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
      toast('Blog rejected.', { icon: '🚫' })
      onDecision({ status: 'REJECTED', rejection_reason: reason.trim() })
      setRejecting(false)
      setReason('')
    } catch (err: any) {
      toast.error(err.message || 'Rejection failed')
    } finally {
      setLoadingRej(false)
    }
  }

  return (
    <div style={{
      background: 'linear-gradient(135deg, rgba(245,158,11,0.05), rgba(139,92,246,0.04))',
      border: '1px solid rgba(245,158,11,0.22)',
      borderRadius: 14,
      padding: '18px 20px',
      backdropFilter: 'blur(16px)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{
          width: 28, height: 28,
          background: 'rgba(245,158,11,0.1)',
          border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Eye size={13} color="var(--amber-400)" />
        </div>
        <div>
          <div style={{
            fontFamily: '"Space Grotesk", sans-serif',
            fontWeight: 600, color: 'var(--amber-400)', fontSize: 13,
          }}>
            Awaiting Your Review
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Read the blog above, then approve to publish or reject with feedback.
          </div>
        </div>
      </div>

      <div style={{ height: 1, background: 'rgba(245,158,11,0.1)', marginBottom: 14 }} />

      {!rejecting ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn btn-success"
            onClick={handleApprove}
            disabled={loadingApp}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            {loadingApp
              ? <><div className="spinner" style={{ width: 13, height: 13 }} /> Approving…</>
              : <><CheckCircle size={13} /> Approve & Publish</>
            }
          </button>
          <button
            className="btn btn-danger"
            onClick={() => setRejecting(true)}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            <XCircle size={13} /> Reject
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <textarea
            className="input"
            rows={3}
            placeholder="Rejection reason (required)…"
            value={reason}
            onChange={e => setReason(e.target.value)}
            style={{ resize: 'none', fontSize: 13 }}
            autoFocus
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-danger"
              onClick={handleReject}
              disabled={loadingRej || !reason.trim()}
              style={{ flex: 1, justifyContent: 'center' }}
            >
              {loadingRej
                ? <><div className="spinner" style={{ width: 13, height: 13 }} /> Rejecting…</>
                : <><XCircle size={13} /> Confirm Rejection</>
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
