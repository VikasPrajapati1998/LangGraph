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
  const [title,   setTitle]   = useState(blog.blog_title || '')
  const [content, setContent] = useState(blog.content    || '')
  const [saving,  setSaving]  = useState(false)
  const [tab,     setTab]     = useState<'title' | 'content'>('title')

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
      toast.success('Saved!')
      onSaved(updated)
      onClose()
    } catch (err: any) {
      toast.error(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const tabs = [
    { id: 'title',   icon: <Type size={12} />,      label: 'Rename'       },
    { id: 'content', icon: <AlignLeft size={12} />, label: 'Edit Content' },
  ] as const

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(3, 7, 18, 0.88)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="animate-scale-in"
        style={{
          background: 'rgba(13, 22, 41, 0.96)',
          border: '1px solid rgba(139,92,246,0.25)',
          borderRadius: 18,
          width: '100%', maxWidth: 760,
          maxHeight: '92vh',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(139,92,246,0.1), var(--shadow-glow)',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(139,92,246,0.1)',
          background: 'rgba(139,92,246,0.04)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--violet), var(--cyan))',
              boxShadow: '0 0 8px var(--violet)',
            }} />
            <h3 style={{
              fontFamily: '"Space Grotesk", sans-serif',
              fontSize: '1rem', fontWeight: 600,
              color: 'var(--text-bright)', margin: 0,
            }}>
              Edit Blog
            </h3>
          </div>
          <button className="btn btn-ghost" style={{ padding: '5px 7px' }} onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'flex', gap: 2, padding: '8px 20px 0',
          borderBottom: '1px solid rgba(139,92,246,0.08)',
        }}>
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: `2px solid ${tab === t.id ? 'var(--violet)' : 'transparent'}`,
                padding: '7px 14px 10px',
                cursor: 'pointer',
                fontSize: 12.5,
                fontWeight: 500,
                color: tab === t.id ? 'var(--violet-400)' : 'var(--text-dim)',
                fontFamily: '"Space Grotesk", sans-serif',
                transition: 'color 0.2s, border-color 0.2s',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
          {tab === 'title' ? (
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-dim)', display: 'block', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 }}>
                Blog Title
              </label>
              <input
                className="input"
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder="Enter a new title…"
                autoFocus
              />
              <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 8 }}>
                Original topic: <em style={{ color: 'var(--text-mid)' }}>{blog.topic}</em>
              </p>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <label style={{ fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 }}>
                  Markdown Content
                </label>
                <span style={{ fontSize: 10, color: 'var(--text-ghost)' }}>
                  {content.split(/\s+/).filter(Boolean).length} words
                </span>
              </div>
              <textarea
                className="input"
                rows={22}
                value={content}
                onChange={e => setContent(e.target.value)}
                style={{
                  resize: 'vertical',
                  fontFamily: '"Fira Code", monospace',
                  fontSize: 12.5,
                  lineHeight: 1.75,
                }}
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px',
          borderTop: '1px solid rgba(139,92,246,0.08)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
          background: 'rgba(139,92,246,0.02)',
        }}>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving
              ? <><div className="spinner" style={{ width: 13, height: 13 }} /> Saving…</>
              : <><Save size={13} /> Save Changes</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}
