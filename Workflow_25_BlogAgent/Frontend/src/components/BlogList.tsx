import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Filter } from 'lucide-react'
import toast from 'react-hot-toast'
import BlogCard from './BlogCard'
import { listBlogs, deleteBlog } from '../api'
import type { Blog, BlogStatus } from '../types'

interface Props {
  onSelect: (blog: Blog) => void
  refreshKey: number
}

const FILTERS: { label: string; value: string }[] = [
  { label: 'All',       value: '' },
  { label: 'Pending',   value: 'PENDING' },
  { label: 'Published', value: 'COMPLETED' },
  { label: 'Rejected',  value: 'REJECTED' },
  { label: 'Failed',    value: 'FAILED' },
]

export default function BlogList({ onSelect, refreshKey }: Props) {
  const [blogs, setBlogs]     = useState<Blog[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listBlogs(filter || undefined)
      // Sort by created_at descending
      data.sort((a, b) =>
        new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
      )
      setBlogs(data)
    } catch (err: any) {
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
      toast.success('Blog deleted')
      setBlogs(prev => prev.filter(b => b.thread_id !== blog.thread_id))
    } catch (err: any) {
      toast.error(err.message || 'Failed to delete')
    }
  }

  // Group by date
  const grouped = blogs.reduce<Record<string, Blog[]>>((acc, blog) => {
    const day = blog.created_at
      ? new Date(blog.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
      : 'Unknown'
    ;(acc[day] ||= []).push(blog)
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {FILTERS.map(f => (
            <button
              key={f.value}
              className="btn btn-ghost"
              style={{
                padding: '5px 12px',
                fontSize: 12,
                ...(filter === f.value ? {
                  background: 'rgba(251,191,36,0.1)',
                  borderColor: 'rgba(251,191,36,0.4)',
                  color: '#fbbf24',
                } : {}),
              }}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button
          className="btn btn-ghost"
          style={{ padding: '5px 10px' }}
          onClick={load}
          title="Refresh"
        >
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[1, 2, 3].map(i => (
            <div key={i} className="skeleton" style={{ height: 90, borderRadius: 12 }} />
          ))}
        </div>
      ) : blogs.length === 0 ? (
        <div style={{
          textAlign: 'center', padding: '48px 20px',
          color: '#627d98',
          border: '1px dashed rgba(251,191,36,0.1)',
          borderRadius: 12,
        }}>
          <div style={{ fontSize: 36, marginBottom: 10 }}>✍️</div>
          <p style={{ margin: 0, fontSize: 14 }}>No blogs yet. Generate your first one!</p>
        </div>
      ) : (
        Object.entries(grouped).map(([day, dayBlogs]) => (
          <div key={day}>
            <div style={{
              fontSize: 11, fontWeight: 600, letterSpacing: '0.06em',
              color: '#486581', textTransform: 'uppercase',
              marginBottom: 8, paddingLeft: 4,
            }}>
              {day}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {dayBlogs.map(blog => (
                <BlogCard
                  key={blog.thread_id}
                  blog={blog}
                  onSelect={onSelect}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}
