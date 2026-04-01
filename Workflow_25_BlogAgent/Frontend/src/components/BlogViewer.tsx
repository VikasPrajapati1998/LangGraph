import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  ArrowLeft, Edit3, Trash2, RefreshCw,
  Clock, CheckCircle, XCircle, AlertTriangle,
} from 'lucide-react'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'

import StatusBadge from './StatusBadge'
import ApprovalPanel from './ApprovalPanel'
import DownloadMenu from './DownloadMenu'
import EditModal from './EditModal'

import { getBlog, deleteBlog } from '../api'
import { usePolling } from '../hooks/usePolling'
import type { Blog } from '../types'

declare global {
  interface ImportMeta {
    readonly env: Record<string, string>
  }
}

interface Props {
  blog: Blog
  onBack: () => void
  onDeleted: () => void
  onUpdated: (blog: Blog) => void
}

export default function BlogViewer({ blog: initialBlog, onBack, onDeleted, onUpdated }: Props) {
  const [blog,     setBlog]     = useState<Blog>(initialBlog)
  const [editing,  setEditing]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Poll while PENDING or APPROVED (workflow running)
  const isLive = blog.status === 'PENDING' || blog.status === 'APPROVED'

  const refresh = useCallback(async () => {
    try {
      const updated = await getBlog(blog.thread_id)
      setBlog(updated)
      onUpdated(updated)
    } catch { /* silent */ }
  }, [blog.thread_id])

  usePolling(refresh, 4000, isLive)

  // Sync if parent passes a newer version
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

  const isCompleted = blog.status === 'COMPLETED'
  const isRejected  = blog.status === 'REJECTED'
  const isPending   = blog.status === 'PENDING'
  const isFailed    = blog.status === 'FAILED'

  // Image base URL: localhost in dev, relative in production (backend must serve /images)
  const baseImageUrl = (import.meta.env.MODE as string) === 'development' ? 'http://localhost:8000' : ''

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

        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-ghost" onClick={onBack} style={{ padding: '6px 10px' }}>
            <ArrowLeft size={14} /> Back
          </button>

          <StatusBadge status={blog.status} />

          <div style={{ flex: 1 }} />

          {/* Live polling badge */}
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

        {/* Meta card */}
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
                <CheckCircle size={11} /> Approved {dateStr(blog.approved_at)}
              </span>
            )}
            {dateStr(blog.rejected_at) && (
              <span style={{ fontSize: 12, color: '#fb7185', display: 'flex', alignItems: 'center', gap: 4 }}>
                <XCircle size={11} /> Rejected {dateStr(blog.rejected_at)}
              </span>
            )}
          </div>
        </div>

        {/* Approval panel — only for PENDING */}
        {isPending && (
          <ApprovalPanel
            blog={blog}
            onDecision={partial => setBlog(prev => ({ ...prev, ...partial }))}
          />
        )}

        {/* Rejection reason */}
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

        {/* Failed notice */}
        {isFailed && (
          <div style={{
            background: 'rgba(251,113,133,0.08)',
            border: '1px solid rgba(251,113,133,0.25)',
            borderRadius: 10,
            padding: '12px 16px',
            display: 'flex', gap: 10, alignItems: 'center',
          }}>
            <AlertTriangle size={16} color="#fb7185" />
            <span style={{ fontSize: 13, color: '#fb7185' }}>
              Workflow failed. Check server logs for details.
            </span>
          </div>
        )}

        {/* Blog content */}
        {blog.content ? (
          <div className="card" style={{ padding: '28px 32px' }}>
            <div className="prose-blog">
              <ReactMarkdown
                components={{
                  img: ({ src, alt, ...props }) => {
                    if (!src) return null
                    const fullSrc = baseImageUrl + (src.startsWith('/') ? src : `/${src}`)
                    return (
                      <img
                        src={fullSrc}
                        alt={alt || ''}
                        style={{ maxWidth: '100%', height: 'auto', borderRadius: '8px', margin: '20px 0' }}
                        {...props}
                      />
                    )
                  },
                }}
              >
                {blog.content}
              </ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="card" style={{ padding: '48px 32px', textAlign: 'center' }}>
            {isLive ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
                <div className="spinner" style={{ width: 32, height: 32 }} />
                <p style={{ color: '#9fb3c8', margin: 0, fontSize: 14 }}>
                  {blog.status === 'PENDING'
                    ? 'AI is writing your blog… this takes a few minutes.'
                    : 'Generating images and finalising…'}
                </p>
                {/* Skeleton lines */}
                <div style={{ width: '100%', maxWidth: 480, display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                  {[90, 75, 85, 60, 80].map((w, i) => (
                    <div key={i} className="skeleton" style={{ height: 12, width: `${w}%` }} />
                  ))}
                </div>
              </div>
            ) : (
              <p style={{ color: '#627d98', margin: 0 }}>No content available.</p>
            )}
          </div>
        )}

        {/* Word count footer */}
        {blog.content && (
          <div style={{
            textAlign: 'right', fontSize: 11, color: '#486581',
          }}>
            {blog.content.split(/\s+/).filter(Boolean).length} words ·{' '}
            {blog.content.length} characters
          </div>
        )}
      </div>
    </>
  )
}
