import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  ArrowLeft, Edit3, Trash2, RefreshCw,
  Clock, CheckCircle, XCircle, ExternalLink, Globe,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'

import StatusBadge   from './StatusBadge'
import ApprovalPanel from './ApprovalPanel'
import DownloadMenu  from './DownloadMenu'
import EditModal     from './EditModal'

import { getBlog, deleteBlog } from '../api'
import { usePolling }           from '../hooks/usePolling'
import type { Blog }            from '../types'

interface Props {
  blog: Blog
  onBack: () => void
  onDeleted: () => void
  onUpdated: (blog: Blog) => void
}

/** Mirror of Python's _sanitize_filename in agent.py */
function sanitizeSlug(name: string): string {
  return name
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, '_')
    .replace(/-+/g, '-')
    .replace(/^[ \-_]+|[ \-_]+$/g, '')
}

export default function BlogViewer({ blog: initialBlog, onBack, onDeleted, onUpdated }: Props) {
  const [blog,     setBlog]     = useState<Blog>(initialBlog)
  const [editing,  setEditing]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Only poll while the workflow is still running (PENDING)
  // APPROVED and REJECTED are both terminal states
  const isLive = blog.status === 'PENDING'

  const refresh = useCallback(async () => {
    try {
      const updated = await getBlog(blog.thread_id)
      setBlog(updated)
      onUpdated(updated)
    } catch { /* silent */ }
  }, [blog.thread_id])

  usePolling(refresh, 4000, isLive)

  // Sync when parent passes a newer version
  useEffect(() => { setBlog(initialBlog) }, [initialBlog])

  async function handleDelete() {
    if (!confirm(`Permanently delete "${blog.blog_title || blog.topic}"?`)) return
    setDeleting(true)
    try {
      await deleteBlog(blog.thread_id)
      toast.success('Blog deleted')
      onDeleted()
    } catch (err: any) {
      toast.error(err.message || 'Delete failed')
      setDeleting(false)
    }
  }

  async function handleManualRefresh() {
    setLoading(true)
    await refresh()
    setLoading(false)
  }

  const dateStr = (d: string | null) =>
    d ? format(parseISO(d), 'MMM d, yyyy · h:mm a') : null

  const isApproved = blog.status === 'APPROVED'
  const isRejected = blog.status === 'REJECTED'
  const isPending  = blog.status === 'PENDING'

  // URL for the published HTML page (served by FastAPI at /site)
  const slug    = blog.blog_title ? sanitizeSlug(blog.blog_title) : null
  const htmlUrl = isApproved && slug
    ? `/site/contents/html/${slug}.html`
    : null

  return (
    <>
      {editing && (
        <EditModal
          blog={blog}
          onSaved={updated => { setBlog(updated); onUpdated(updated) }}
          onClose={() => setEditing(false)}
        />
      )}

      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* ── Top bar ── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-ghost" onClick={onBack} style={{ padding: '6px 10px' }}>
            <ArrowLeft size={14} /> Back
          </button>

          <StatusBadge status={blog.status} />

          <div style={{ flex: 1 }} />

          {/* Live polling indicator */}
          {isLive && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 12, color: '#fbbf24',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#fbbf24',
                animation: 'pulse 1.5s ease-in-out infinite',
              }} />
              Live updating…
            </div>
          )}

          <button
            className="btn btn-ghost"
            onClick={handleManualRefresh}
            style={{ padding: '6px 8px' }}
            title="Refresh"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>

          {/* Open published page in new tab */}
          {htmlUrl && (
            <a
              href={htmlUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
              style={{ gap: 6 }}
              title="Open published page in new tab"
            >
              <ExternalLink size={14} /> Open Page
            </a>
          )}

          {blog.content && (
            <>
              <DownloadMenu
                content={blog.content}
                title={blog.blog_title || blog.topic}
              />
              <button
                className="btn btn-ghost"
                onClick={() => setEditing(true)}
                style={{ gap: 6 }}
              >
                <Edit3 size={14} /> Edit
              </button>
            </>
          )}

          <button
            className="btn btn-red"
            onClick={handleDelete}
            disabled={deleting}
            style={{ padding: '6px 10px' }}
          >
            {deleting
              ? <div className="spinner" style={{ width: 14, height: 14 }} />
              : <Trash2 size={14} />
            }
          </button>
        </div>

        {/* ── Meta card ── */}
        <div className="card" style={{ padding: '16px 20px' }}>
          <h1 style={{
            fontFamily: '"Playfair Display", serif',
            fontSize: '1.6rem', fontWeight: 700,
            color: '#e8edf2', margin: '0 0 8px',
            lineHeight: 1.25,
          }}>
            {blog.blog_title || blog.topic}
          </h1>
          {blog.blog_title && (
            <p style={{ fontSize: 13, color: '#627d98', margin: '0 0 12px' }}>
              Topic: {blog.topic}
            </p>
          )}

          {/* Timeline */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 24px' }}>
            {dateStr(blog.created_at) && (
              <span style={{ fontSize: 12, color: '#486581', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={11} /> Created {dateStr(blog.created_at)}
              </span>
            )}
            {dateStr(blog.approved_at) && (
              <span style={{ fontSize: 12, color: '#34d399', display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle size={11} /> Published {dateStr(blog.approved_at)}
              </span>
            )}
            {dateStr(blog.rejected_at) && (
              <span style={{ fontSize: 12, color: '#fb7185', display: 'flex', alignItems: 'center', gap: 4 }}>
                <XCircle size={11} /> Rejected {dateStr(blog.rejected_at)}
              </span>
            )}
          </div>
        </div>

        {/* ── Approval panel — only for PENDING ── */}
        {isPending && blog.content && (
          <ApprovalPanel
            blog={blog}
            onDecision={partial => setBlog(prev => ({ ...prev, ...partial }))}
          />
        )}

        {/* ── Rejection reason ── */}
        {isRejected && blog.rejection_reason && (
          <div style={{
            background: 'rgba(251,113,133,0.08)',
            border: '1px solid rgba(251,113,133,0.25)',
            borderRadius: 10,
            padding: '12px 16px',
            display: 'flex', gap: 10, alignItems: 'flex-start',
          }}>
            <XCircle size={16} color="#fb7185" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#fb7185', marginBottom: 4 }}>
                Rejection Reason
              </div>
              <div style={{ fontSize: 13, color: '#c9d8e8' }}>{blog.rejection_reason}</div>
            </div>
          </div>
        )}

        {/* ── Content area ── */}

        {/* APPROVED → iframe of the published HTML page */}
        {isApproved && htmlUrl && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Published banner */}
            <div style={{
              background: 'rgba(52,211,153,0.07)',
              border: '1px solid rgba(52,211,153,0.25)',
              borderRadius: 10,
              padding: '12px 18px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <Globe size={16} color="#34d399" style={{ flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#34d399' }}>
                  Blog Published
                </span>
                <span style={{ fontSize: 12, color: '#6ee7b7', marginLeft: 10 }}>
                  Live at&nbsp;
                  <a
                    href={htmlUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: '#34d399', textDecoration: 'underline' }}
                  >
                    {htmlUrl}
                  </a>
                </span>
              </div>
              <a
                href={htmlUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-green"
                style={{ fontSize: 12, padding: '5px 12px', gap: 5 }}
              >
                <ExternalLink size={12} /> Open
              </a>
            </div>

            {/* iframe preview */}
            <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
              <iframe
                src={htmlUrl}
                title={blog.blog_title || blog.topic}
                style={{
                  width: '100%',
                  height: '80vh',
                  border: 'none',
                  display: 'block',
                  borderRadius: 12,
                }}
              />
            </div>
          </div>
        )}

        {/* PENDING with content → Markdown preview for review */}
        {isPending && blog.content && (
          <div className="card" style={{ padding: '28px 32px' }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: '#fbbf24',
              textTransform: 'uppercase', letterSpacing: '0.07em',
              marginBottom: 16, display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#fbbf24',
                animation: 'pulse 1.5s ease-in-out infinite',
              }} />
              Preview — awaiting your approval
            </div>
            <div className="prose-blog">
              <ReactMarkdown>{blog.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* PENDING without content → spinner + skeleton */}
        {isPending && !blog.content && (
          <div className="card" style={{ padding: '48px 32px', textAlign: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <p style={{ color: '#9fb3c8', margin: 0, fontSize: 14 }}>
                AI is writing your blog… this may take a few minutes.
              </p>
              <div style={{
                width: '100%', maxWidth: 480,
                display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8,
              }}>
                {[90, 75, 85, 60, 80].map((w, i) => (
                  <div key={i} className="skeleton" style={{ height: 12, width: `${w}%` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* REJECTED with content → show for reference */}
        {isRejected && blog.content && (
          <div className="card" style={{ padding: '28px 32px', opacity: 0.7 }}>
            <div style={{
              fontSize: 11, fontWeight: 600, color: '#fb7185',
              textTransform: 'uppercase', letterSpacing: '0.07em',
              marginBottom: 16,
            }}>
              Rejected content — for reference only
            </div>
            <div className="prose-blog">
              <ReactMarkdown>{blog.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Word count footer (not shown for iframe view) */}
        {blog.content && !isApproved && (
          <div style={{ textAlign: 'right', fontSize: 11, color: '#486581' }}>
            {blog.content.split(/\s+/).filter(Boolean).length} words ·{' '}
            {blog.content.length} characters
          </div>
        )}
      </div>
    </>
  )
}
