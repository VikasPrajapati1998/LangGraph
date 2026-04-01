import { useState } from 'react'
import { Sparkles, Wand2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { generateBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  onGenerated: (blog: Partial<Blog> & { thread_id: string }) => void
}

const SUGGESTIONS = [
  'The Future of Quantum Computing',
  'Building RAG Systems with LangGraph',
  'WebAssembly: Beyond the Browser',
]

export default function GenerateForm({ onGenerated }: Props) {
  const [topic,   setTopic]   = useState('')
  const [loading, setLoading] = useState(false)
  const [focused, setFocused] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim()) return
    setLoading(true)
    try {
      const res = await generateBlog(topic.trim())
      toast.success('Blog generation started!')
      onGenerated({ thread_id: res.thread_id, topic: topic.trim(), status: 'PENDING' } as any)
      setTopic('')
    } catch (err: any) {
      toast.error(err.message || 'Failed to start generation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="animate-slide-up"
      style={{
        background: 'rgba(13, 22, 41, 0.7)',
        border: `1px solid ${focused ? 'rgba(139,92,246,0.35)' : 'rgba(139,92,246,0.15)'}`,
        borderRadius: 16,
        padding: '18px',
        backdropFilter: 'blur(20px)',
        transition: 'border-color 0.3s, box-shadow 0.3s',
        boxShadow: focused
          ? '0 0 0 3px rgba(139,92,246,0.08), var(--shadow-glow)'
          : 'var(--shadow-md)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <div style={{
          width: 36, height: 36,
          background: 'linear-gradient(135deg, rgba(139,92,246,0.2), rgba(6,182,212,0.1))',
          border: '1px solid rgba(139,92,246,0.3)',
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 14px rgba(139,92,246,0.15)',
        }}>
          <Wand2 size={16} color="#a78bfa" />
        </div>
        <div>
          <div style={{
            fontFamily: '"Space Grotesk", sans-serif',
            fontSize: '0.95rem', fontWeight: 600,
            color: 'var(--text-bright)',
          }}>
            Generate Blog
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 1 }}>
            AI writes · you approve
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          className="input"
          rows={3}
          placeholder="Enter a topic… e.g. 'Deep dive into transformer attention'"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={loading}
          style={{ resize: 'none', marginBottom: 10, fontSize: 13 }}
        />

        {/* Suggestions */}
        {!topic && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 5, marginBottom: 10,
          }}>
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => setTopic(s)}
                style={{
                  background: 'rgba(139,92,246,0.06)',
                  border: '1px solid rgba(139,92,246,0.15)',
                  borderRadius: 6, padding: '3px 9px',
                  fontSize: 10.5, color: 'var(--text-dim)',
                  cursor: 'pointer', fontFamily: '"Inter", sans-serif',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--violet-300)'
                  ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(139,92,246,0.35)'
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(139,92,246,0.12)'
                }}
                onMouseLeave={e => {
                  ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-dim)'
                  ;(e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(139,92,246,0.15)'
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(139,92,246,0.06)'
                }}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !topic.trim()}
          style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: 13 }}
        >
          {loading ? (
            <><div className="spinner" style={{ width: 14, height: 14 }} /> Starting…</>
          ) : (
            <><Sparkles size={14} /> Generate Blog</>
          )}
        </button>
      </form>
    </div>
  )
}
