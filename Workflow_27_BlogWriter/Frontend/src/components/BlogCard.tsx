import { format, parseISO } from 'date-fns'
import { Eye, Trash2, Clock, ExternalLink } from 'lucide-react'
import StatusBadge from './StatusBadge'
import type { Blog } from '../types'

interface Props {
  blog: Blog
  onSelect: (blog: Blog) => void
  onDelete: (blog: Blog) => void
}

function sanitizeSlug(name: string): string {
  return name
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, '_')
    .replace(/-+/g, '-')
    .replace(/^[ \-_]+|[ \-_]+$/g, '')
}

export default function BlogCard({ blog, onSelect, onDelete }: Props) {
  const date = blog.created_at
    ? format(parseISO(blog.created_at), 'MMM d · h:mm a')
    : 'Unknown'

  const isPending  = blog.status === 'PENDING'
  const isApproved = blog.status === 'APPROVED'
  const isRejected = blog.status === 'REJECTED'

  const htmlUrl = isApproved && blog.blog_title
    ? `/site/contents/html/${sanitizeSlug(blog.blog_title)}.html`
    : null

  const borderColor = isPending  ? 'rgba(245,158,11,0.18)'
                    : isApproved ? 'rgba(16,185,129,0.18)'
                    : 'rgba(244,63,94,0.12)'

  const hoverBorder = isPending  ? 'rgba(245,158,11,0.38)'
                    : isApproved ? 'rgba(16,185,129,0.35)'
                    : 'rgba(244,63,94,0.28)'

  return (
    <div
      className="animate-slide-up"
      style={{
        background: 'rgba(13, 22, 41, 0.65)',
        border: `1px solid ${borderColor}`,
        borderRadius: 12,
        padding: '13px 15px',
        cursor: 'pointer',
        backdropFilter: 'blur(16px)',
        transition: 'all 0.22s cubic-bezier(0.16,1,0.3,1)',
      }}
      onClick={() => onSelect(blog)}
      onMouseEnter={e => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = hoverBorder
        el.style.transform = 'translateX(2px)'
        el.style.boxShadow = isPending
          ? '0 4px 20px rgba(245,158,11,0.1), -2px 0 0 rgba(245,158,11,0.4)'
          : isApproved
            ? '0 4px 20px rgba(16,185,129,0.1), -2px 0 0 rgba(16,185,129,0.4)'
            : '0 4px 20px rgba(244,63,94,0.08), -2px 0 0 rgba(244,63,94,0.3)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = borderColor
        el.style.transform = 'translateX(0)'
        el.style.boxShadow = 'none'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        {/* Left */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 6 }}>
            <StatusBadge status={blog.status} />
          </div>

          <h3 style={{
            fontFamily: '"Space Grotesk", sans-serif',
            fontSize: '0.88rem', fontWeight: 600,
            color: 'var(--text-bright)',
            margin: '0 0 3px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            lineHeight: 1.35,
          }}>
            {blog.blog_title || blog.topic}
          </h3>

          {blog.blog_title && (
            <p style={{
              fontSize: 11, color: 'var(--text-dim)', margin: 0,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {blog.topic}
            </p>
          )}

          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            marginTop: 7, color: 'var(--text-dim)', fontSize: 10,
          }}>
            <Clock size={9} />
            {date}
          </div>

          {/* Status sub-label */}
          {isPending && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              marginTop: 5, fontSize: 10, color: 'var(--amber-400)',
              fontFamily: '"Space Grotesk", sans-serif', fontWeight: 500,
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--amber-400)',
                boxShadow: '0 0 6px var(--amber-400)',
                animation: 'dotBlink 1.6s ease-in-out infinite',
              }} />
              Awaiting review
            </div>
          )}
          {isApproved && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              marginTop: 5, fontSize: 10, color: 'var(--emerald)',
              fontFamily: '"Space Grotesk", sans-serif', fontWeight: 500,
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--emerald)',
                boxShadow: '0 0 6px var(--emerald)',
              }} />
              Live on site
            </div>
          )}
          {isRejected && blog.rejection_reason && (
            <div style={{
              marginTop: 5, fontSize: 10, color: 'var(--rose-400)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {blog.rejection_reason}
            </div>
          )}
        </div>

        {/* Actions */}
        <div
          style={{ display: 'flex', gap: 5, flexShrink: 0, alignItems: 'center' }}
          onClick={e => e.stopPropagation()}
        >
          <button
            className="btn btn-ghost"
            style={{ padding: '5px 8px', fontSize: 11 }}
            onClick={() => onSelect(blog)}
            title="View"
          >
            <Eye size={12} />
          </button>

          {htmlUrl && (
            <a
              href={htmlUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
              style={{ padding: '5px 8px' }}
              title="Open published page"
            >
              <ExternalLink size={12} />
            </a>
          )}

          <button
            className="btn btn-danger"
            style={{ padding: '5px 8px', fontSize: 11 }}
            onClick={() => onDelete(blog)}
            title="Delete"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    </div>
  )
}
