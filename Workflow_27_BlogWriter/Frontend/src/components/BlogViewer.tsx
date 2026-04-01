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

  const isLive     = blog.status === 'PENDING'
  const isApproved = blog.status === 'APPROVED'
  const isRejected = blog.status === 'REJECTED'
  const isPending  = blog.status === 'PENDING'

  const slug    = blog.blog_title ? sanitizeSlug(blog.blog_title) : null
  const htmlUrl = isApproved && slug ? `/site/contents/html/${slug}.html` : null

  const refresh = useCallback(async () => {
    try {
      const updated = await getBlog(blog.thread_id)
      setBlog(updated)
      onUpdated(updated)
    } catch { /* silent */ }
  }, [blog.thread_id])

  usePolling(refresh, 4000, isLive)
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

  const dateStr = (d: string | null) =>
    d ? format(parseISO(d), 'MMM d, yyyy · h:mm a') : null

  return (
    <>
      {editing && (
        <EditModal
          blog={blog}
          onSaved={updated => { setBlog(updated); onUpdated(updated) }}
          onClose={() => setEditing(false)}
        />
      )}

      <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* ── Top bar ── */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
          background: 'rgba(13,22,41,0.5)',
          border: '1px solid rgba(139,92,246,0.1)',
          borderRadius: 12,
          padding: '10px 14px',
          backdropFilter: 'blur(16px)',
        }}>
          <button className="btn btn-ghost" onClick={onBack} style={{ padding: '5px 10px', fontSize: 12 }}>
            <ArrowLeft size={12} /> Back
          </button>

          <StatusBadge status={blog.status} />

          {isLive && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 11, color: 'var(--amber-400)',
              fontFamily: '"Space Grotesk", sans-serif',
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--amber-400)',
                boxShadow: '0 0 6px var(--amber-400)',
                animation: 'dotBlink 1.4s ease-in-out infinite',
              }} />
              AI writing…
            </div>
          )}

          <div style={{ flex: 1 }} />

          <button
            className="btn btn-ghost"
            onClick={async () => { setLoading(true); await refresh(); setLoading(false) }}
            style={{ padding: '5px 8px' }} title="Refresh"
          >
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>

          {htmlUrl && (
            <a
              href={htmlUrl} target="_blank" rel="noopener noreferrer"
              className="btn btn-cyan" style={{ fontSize: 12, padding: '5px 12px', gap: 5 }}
            >
              <ExternalLink size={12} /> Open Page
            </a>
          )}

          {blog.content && (
            <>
              <DownloadMenu content={blog.content} title={blog.blog_title || blog.topic} />
              <button className="btn btn-ghost" onClick={() => setEditing(true)} style={{ fontSize: 12 }}>
                <Edit3 size={12} /> Edit
              </button>
            </>
          )}

          <button
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={deleting}
            style={{ padding: '5px 9px' }}
          >
            {deleting
              ? <div className="spinner" style={{ width: 12, height: 12 }} />
              : <Trash2 size={12} />
            }
          </button>
        </div>

        {/* ── Meta card ── */}
        <div style={{
          background: 'rgba(13,22,41,0.65)',
          border: '1px solid rgba(139,92,246,0.12)',
          borderRadius: 14,
          padding: '18px 22px',
          backdropFilter: 'blur(20px)',
        }}>
          <h1 style={{
            fontFamily: '"Space Grotesk", sans-serif',
            fontSize: '1.55rem', fontWeight: 700,
            color: 'var(--text-bright)', margin: '0 0 6px',
            lineHeight: 1.25,
            letterSpacing: '-0.02em',
          }}>
            {blog.blog_title || blog.topic}
          </h1>
          {blog.blog_title && (
            <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: '0 0 12px', fontStyle: 'italic' }}>
              Topic: {blog.topic}
            </p>
          )}

          <div style={{ height: 1, background: 'var(--glow-line, linear-gradient(90deg,transparent,rgba(139,92,246,0.3),transparent))', marginBottom: 12 }} />

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 20px' }}>
            {dateStr(blog.created_at) && (
              <span style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <Clock size={10} color="var(--text-dim)" /> {dateStr(blog.created_at)}
              </span>
            )}
            {dateStr(blog.approved_at) && (
              <span style={{ fontSize: 11, color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle size={10} /> Published {dateStr(blog.approved_at)}
              </span>
            )}
            {dateStr(blog.rejected_at) && (
              <span style={{ fontSize: 11, color: 'var(--rose-400)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <XCircle size={10} /> Rejected {dateStr(blog.rejected_at)}
              </span>
            )}
          </div>
        </div>

        {/* ── Approval panel ── */}
        {isPending && blog.content && (
          <ApprovalPanel blog={blog} onDecision={partial => setBlog(prev => ({ ...prev, ...partial }))} />
        )}

        {/* ── Rejection reason ── */}
        {isRejected && blog.rejection_reason && (
          <div style={{
            background: 'rgba(244,63,94,0.05)',
            border: '1px solid rgba(244,63,94,0.2)',
            borderRadius: 12, padding: '12px 16px',
            display: 'flex', gap: 10, alignItems: 'flex-start',
          }}>
            <XCircle size={14} color="var(--rose-400)" style={{ flexShrink: 0, marginTop: 1 }} />
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--rose-400)', marginBottom: 4, fontFamily: '"Space Grotesk", sans-serif', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Rejection Reason
              </div>
              <div style={{ fontSize: 13, color: '#c9d8e8' }}>{blog.rejection_reason}</div>
            </div>
          </div>
        )}

        {/* ── APPROVED → iframe ── */}
        {isApproved && htmlUrl && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{
              background: 'rgba(16,185,129,0.06)',
              border: '1px solid rgba(16,185,129,0.22)',
              borderRadius: 12, padding: '11px 16px',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <Globe size={14} color="var(--emerald)" style={{ flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: 'var(--emerald)', fontWeight: 500, fontFamily: '"Space Grotesk", sans-serif', flex: 1 }}>
                Published ·{' '}
                <a href={htmlUrl} target="_blank" rel="noopener noreferrer"
                  style={{ color: '#6ee7b7', textDecoration: 'underline', textUnderlineOffset: 3 }}>
                  {htmlUrl}
                </a>
              </span>
              <a href={htmlUrl} target="_blank" rel="noopener noreferrer"
                className="btn btn-success" style={{ fontSize: 11, padding: '4px 10px' }}>
                <ExternalLink size={11} /> Open
              </a>
            </div>

            <div style={{
              background: 'rgba(13,22,41,0.5)',
              border: '1px solid rgba(139,92,246,0.12)',
              borderRadius: 14, overflow: 'hidden',
              boxShadow: 'var(--shadow-lg)',
            }}>
              <iframe
                src={htmlUrl}
                title={blog.blog_title || blog.topic}
                style={{ width: '100%', height: '78vh', border: 'none', display: 'block' }}
              />
            </div>
          </div>
        )}

        {/* ── PENDING + has content → markdown review ── */}
        {isPending && blog.content && (
          <div style={{
            background: 'rgba(13,22,41,0.65)',
            border: '1px solid rgba(245,158,11,0.15)',
            borderRadius: 14, padding: '26px 30px',
            backdropFilter: 'blur(20px)',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginBottom: 20,
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--amber-400)',
                boxShadow: '0 0 8px var(--amber-400)',
                animation: 'dotBlink 1.8s ease-in-out infinite',
              }} />
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
                textTransform: 'uppercase', color: 'var(--amber-400)',
                fontFamily: '"Space Grotesk", sans-serif',
              }}>
                Preview — pending approval
              </span>
            </div>
            <div className="prose-blog">
              <ReactMarkdown>{blog.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* ── PENDING without content → skeleton ── */}
        {isPending && !blog.content && (
          <div style={{
            background: 'rgba(13,22,41,0.65)',
            border: '1px solid rgba(139,92,246,0.1)',
            borderRadius: 14, padding: '52px 32px',
            textAlign: 'center', backdropFilter: 'blur(20px)',
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
              <div className="spinner" style={{ width: 34, height: 34, borderWidth: 3 }} />
              <div>
                <p style={{ color: 'var(--text-mid)', margin: '0 0 4px', fontSize: 14, fontWeight: 500 }}>
                  AI is crafting your blog…
                </p>
                <p style={{ color: 'var(--text-dim)', margin: 0, fontSize: 12 }}>
                  This typically takes 2–5 minutes.
                </p>
              </div>
              <div style={{ width: '100%', maxWidth: 460, display: 'flex', flexDirection: 'column', gap: 9, marginTop: 4 }}>
                {[85, 70, 90, 55, 78, 65].map((w, i) => (
                  <div key={i} className="skeleton" style={{ height: 11, width: `${w}%` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── REJECTED with content ── */}
        {isRejected && blog.content && (
          <div style={{
            background: 'rgba(13,22,41,0.5)',
            border: '1px solid rgba(244,63,94,0.1)',
            borderRadius: 14, padding: '26px 30px',
            opacity: 0.65,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.1em',
              textTransform: 'uppercase', color: 'var(--rose-400)',
              fontFamily: '"Space Grotesk", sans-serif', marginBottom: 18,
            }}>
              Rejected content — reference only
            </div>
            <div className="prose-blog">
              <ReactMarkdown>{blog.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Word count */}
        {blog.content && !isApproved && (
          <div style={{
            textAlign: 'right', fontSize: 10, color: 'var(--text-ghost)',
            fontFamily: '"Space Grotesk", sans-serif',
          }}>
            {blog.content.split(/\s+/).filter(Boolean).length} words ·{' '}
            {blog.content.length.toLocaleString()} chars
          </div>
        )}
      </div>
    </>
  )
}
