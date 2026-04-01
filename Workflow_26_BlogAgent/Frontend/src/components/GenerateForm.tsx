import { useState } from 'react'
import { Sparkles, Feather } from 'lucide-react'
import toast from 'react-hot-toast'
import { generateBlog } from '../api'
import type { Blog } from '../types'

interface Props {
  onGenerated: (blog: Partial<Blog> & { thread_id: string }) => void
}

export default function GenerateForm({ onGenerated }: Props) {
  const [topic, setTopic]     = useState('')
  const [loading, setLoading] = useState(false)

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
    <div className="card p-6 animate-slide-up" style={{ borderColor: 'rgba(251,191,36,0.2)' }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div style={{
          width: 40, height: 40,
          background: 'rgba(251,191,36,0.1)',
          border: '1px solid rgba(251,191,36,0.25)',
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Feather size={18} color="#fbbf24" />
        </div>
        <div>
          <h2 style={{
            fontFamily: '"Playfair Display", serif',
            fontSize: '1.1rem',
            fontWeight: 600,
            color: '#e8edf2',
            margin: 0,
          }}>
            Generate New Blog
          </h2>
          <p style={{ fontSize: 12, color: '#627d98', margin: 0 }}>
            AI writes, you approve
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          className="input"
          rows={3}
          placeholder="Enter your blog topic… e.g. 'Deep dive into transformer attention mechanisms'"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          style={{ resize: 'none', marginBottom: 12 }}
          disabled={loading}
        />
        <button
          type="submit"
          className="btn btn-gold"
          disabled={loading || !topic.trim()}
          style={{ width: '100%', justifyContent: 'center', padding: '10px 16px' }}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: 16, height: 16 }} />
              Starting generation…
            </>
          ) : (
            <>
              <Sparkles size={15} />
              Generate Blog
            </>
          )}
        </button>
      </form>
    </div>
  )
}
