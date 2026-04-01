import { useState, useEffect } from 'react'
import { X, Save, Type, AlignLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { updateBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  blog: Blog
  onSaved: (updated: Blog) => void
  onClose: () => void
}

export default function EditModal({ blog, onSaved, onClose }: Props) {
  const [title,   setTitle]   = useState(blog.blog_title   || '')
  const [content, setContent] = useState(blog.content      || '')
  const [saving,  setSaving]  = useState(false)
  const [tab,     setTab]     = useState<'title' | 'content'>('title')

  // Prevent background scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  async function handleSave() {
    if (!content.trim()) { toast.error('Content cannot be empty'); return }
    setSaving(true)
    try {
      const updated = await updateBlog(blog.thread_id, {
        blog_title: title.trim() || undefined,
        content:    content.trim(),
      })
      toast.success('Blog saved!')
      onSaved(updated)
      onClose()
    } catch (err: any) {
      toast.error(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(6,14,26,0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="animate-slide-up"
        style={{
          background: '#132844',
          border: '1px solid rgba(251,191,36,0.2)',
          borderRadius: 16,
          width: '100%',
          maxWidth: 780,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(251,191,36,0.1)',
        }}>
          <h3 style={{
            fontFamily: '"Playfair Display", serif',
            fontSize: '1.1rem', fontWeight: 600,
            color: '#e8edf2', margin: 0,
          }}>
            Edit Blog
          </h3>
          <button
            className="btn btn-ghost"
            style={{ padding: '6px 8px' }}
            onClick={onClose}
          >
            <X size={15} />
          </button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: 4,
          padding: '10px 20px 0',
          borderBottom: '1px solid rgba(251,191,36,0.1)',
        }}>
          {(['title', 'content'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: `2px solid ${tab === t ? '#fbbf24' : 'transparent'}`,
                padding: '6px 14px 10px',
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 500,
                color: tab === t ? '#fbbf24' : '#627d98',
                fontFamily: '"DM Sans", sans-serif',
                transition: 'color 0.2s',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {t === 'title' ? <Type size={13} /> : <AlignLeft size={13} />}
              {t === 'title' ? 'Rename' : 'Edit Content'}
            </button>
          ))}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {tab === 'title' ? (
            <div>
              <label style={{ fontSize: 12, color: '#627d98', display: 'block', marginBottom: 8 }}>
                Blog Title
              </label>
              <input
                className="input"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Enter a new title…"
                autoFocus
              />
              <p style={{ fontSize: 12, color: '#486581', marginTop: 8 }}>
                Original topic: <em style={{ color: '#627d98' }}>{blog.topic}</em>
              </p>
            </div>
          ) : (
            <div>
              <label style={{ fontSize: 12, color: '#627d98', display: 'block', marginBottom: 8 }}>
                Markdown Content
              </label>
              <textarea
                className="input"
                rows={20}
                value={content}
                onChange={e => setContent(e.target.value)}
                style={{
                  resize: 'vertical',
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: 12,
                  lineHeight: 1.7,
                }}
                autoFocus
              />
              <p style={{ fontSize: 12, color: '#486581', marginTop: 6 }}>
                {content.split(/\s+/).filter(Boolean).length} words
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid rgba(251,191,36,0.1)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-gold"
            onClick={handleSave}
            disabled={saving}
          >
            {saving
              ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Saving…</>
              : <><Save size={14} /> Save Changes</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}
