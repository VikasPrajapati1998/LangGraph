import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, LayoutList } from 'lucide-react'
import toast from 'react-hot-toast'
import BlogCard from './BlogCard'
import { listBlogs, deleteBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  onSelect: (blog: Blog) => void
  refreshKey: number
}

const FILTERS = [
  { label: 'All',       value: '',         color: 'var(--violet-400)'  },
  { label: 'Pending',   value: 'PENDING',  color: 'var(--amber-400)'   },
  { label: 'Published', value: 'APPROVED', color: 'var(--emerald)'     },
  { label: 'Rejected',  value: 'REJECTED', color: 'var(--rose-400)'    },
]

export default function BlogList({ onSelect, refreshKey }: Props) {
  const [blogs,   setBlogs]   = useState<Blog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listBlogs(filter || undefined)
      data.sort((a, b) =>
        new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
      )
      setBlogs(data)
    } catch {
      toast.error('Failed to load blogs')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => { load() }, [load, refreshKey])

  async function handleDelete(blog: Blog) {
    if (!confirm(`Delete "${blog.blog_title || blog.topic}"?`)) return
    try {
      await deleteBlog(blog.thread_id)
      toast.success('Deleted')
      setBlogs(prev => prev.filter(b => b.thread_id !== blog.thread_id))
    } catch (err: any) {
      toast.error(err.message || 'Delete failed')
    }
  }

  const grouped = blogs.reduce<Record<string, Blog[]>>((acc, blog) => {
    const day = blog.created_at
      ? new Date(blog.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
        })
      : 'Unknown'
    ;(acc[day] ||= []).push(blog)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ display: 'flex', gap: 4, flex: 1, flexWrap: 'wrap' }}>
          {FILTERS.map(f => {
            const active = filter === f.value
            return (
              <button
                key={f.value}
                style={{
                  padding: '4px 10px',
                  borderRadius: 7,
                  fontSize: 11,
                  fontWeight: 500,
                  fontFamily: '"Space Grotesk", sans-serif',
                  cursor: 'pointer',
                  border: 'none',
                  transition: 'all 0.18s',
                  background: active ? `rgba(${f.color === 'var(--violet-400)' ? '139,92,246' : f.color === 'var(--amber-400)' ? '245,158,11' : f.color === 'var(--emerald)' ? '16,185,129' : '244,63,94'}, 0.15)` : 'rgba(139,92,246,0.04)',
                  color: active ? f.color : 'var(--text-dim)',
                  borderTop: '1px solid transparent',
                  borderBottom: active ? `1px solid ${f.color}` : '1px solid transparent',
                  borderLeft: '1px solid transparent',
                  borderRight: '1px solid transparent',
                }}
                onClick={() => setFilter(f.value)}
              >
                {f.label}
              </button>
            )
          })}
        </div>
        <button
          className="btn btn-ghost"
          style={{ padding: '5px 8px', flexShrink: 0 }}
          onClick={load}
          title="Refresh"
        >
          <RefreshCw size={11} style={{ transition: 'transform 0.4s' }}
            className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: 88, borderRadius: 12 }} />
          ))}
        </div>
      ) : blogs.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '36px 16px',
          color: 'var(--text-ghost)',
          border: '1px dashed rgba(139,92,246,0.1)',
          borderRadius: 12,
        }}>
          <LayoutList size={28} style={{ margin: '0 auto 10px', opacity: 0.3 }} />
          <p style={{ margin: 0, fontSize: 12 }}>
            {filter ? `No ${filter.toLowerCase()} blogs found.` : 'No blogs yet — generate your first one!'}
          </p>
        </div>
      ) : (
        Object.entries(grouped).map(([day, dayBlogs]) => (
          <div key={day}>
            <div style={{
              fontSize: 9.5, fontWeight: 700, letterSpacing: '0.09em',
              color: 'var(--text-ghost)', textTransform: 'uppercase',
              marginBottom: 6, paddingLeft: 3,
              fontFamily: '"Space Grotesk", sans-serif',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              {day}
              <div style={{ height: 1, flex: 1, background: 'rgba(139,92,246,0.08)' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {dayBlogs.map((blog, i) => (
                <div key={blog.thread_id} style={{ animationDelay: `${i * 40}ms` }}>
                  <BlogCard blog={blog} onSelect={onSelect} onDelete={handleDelete} />
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
