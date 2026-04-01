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
    ? format(parseISO(blog.created_at), 'MMM d, yyyy · h:mm a')
    : 'Unknown date'

  const isPending  = blog.status === 'PENDING'
  const isApproved = blog.status === 'APPROVED'

  const htmlUrl = isApproved && blog.blog_title
    ? `/site/contents/html/${sanitizeSlug(blog.blog_title)}.html`
    : null

  return (
    <div
      className="card animate-slide-up"
      style={{ padding: '16px 20px', cursor: 'pointer' }}
      onClick={() => onSelect(blog)}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        {/* Left */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ marginBottom: 6 }}>
            <StatusBadge status={blog.status} />
          </div>
          <h3 style={{
            fontFamily: '"Playfair Display", serif',
            fontSize: '1rem',
            fontWeight: 600,
            color: '#e8edf2',
            margin: '0 0 4px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {blog.blog_title || blog.topic}
          </h3>
          {blog.blog_title && (
            <p style={{
              fontSize: 12, color: '#627d98', margin: 0,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {blog.topic}
            </p>
          )}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            marginTop: 8, color: '#486581', fontSize: 11,
          }}>
            <Clock size={11} />
            {date}
          </div>

          {/* Pending — awaiting review pulse */}
          {isPending && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              marginTop: 6, fontSize: 11, color: '#fbbf24',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#fbbf24',
                animation: 'pulse 1.5s ease-in-out infinite',
              }} />
              Awaiting your review
            </div>
          )}

          {/* Approved — live on site */}
          {isApproved && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              marginTop: 6, fontSize: 11, color: '#34d399',
            }}>
              <div style={{
                width: 6, height: 6, borderRadius: '50%',
                background: '#34d399',
              }} />
              Live on site
            </div>
          )}
        </div>

        {/* Actions */}
        <div
          style={{ display: 'flex', gap: 6, flexShrink: 0 }}
          onClick={e => e.stopPropagation()}
        >
          <button
            className="btn btn-ghost"
            style={{ padding: '6px 10px' }}
            onClick={() => onSelect(blog)}
            title="View blog"
          >
            <Eye size={13} />
          </button>

          {htmlUrl && (
            <a
              href={htmlUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost"
              style={{ padding: '6px 10px' }}
              title="Open published page"
            >
              <ExternalLink size={13} />
            </a>
          )}

          <button
            className="btn btn-red"
            style={{ padding: '6px 10px' }}
            onClick={() => onDelete(blog)}
            title="Delete blog"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  )
}
