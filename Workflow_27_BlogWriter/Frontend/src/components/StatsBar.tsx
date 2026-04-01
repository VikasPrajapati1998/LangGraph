import { useEffect, useState } from 'react'
import { BookOpen, Clock, Globe, XCircle } from 'lucide-react'
import { listBlogs } from '../api'
import type { Blog } from '../types'

interface Props { refreshKey: number }

export default function StatsBar({ refreshKey }: Props) {
  const [blogs, setBlogs] = useState<Blog[]>([])

  useEffect(() => {
    listBlogs(undefined, 200).then(setBlogs).catch(() => {})
  }, [refreshKey])

  const total     = blogs.length
  const pending   = blogs.filter(b => b.status === 'PENDING').length
  const published = blogs.filter(b => b.status === 'APPROVED').length
  const rejected  = blogs.filter(b => b.status === 'REJECTED').length

  const stats = [
    { label: 'Total',     value: total,     icon: <BookOpen size={12} />,  color: 'var(--violet-400)', glow: 'rgba(139,92,246,0.25)' },
    { label: 'Pending',   value: pending,   icon: <Clock size={12} />,     color: 'var(--amber-400)',  glow: 'rgba(245,158,11,0.2)'  },
    { label: 'Published', value: published, icon: <Globe size={12} />,     color: 'var(--emerald)',    glow: 'rgba(16,185,129,0.2)'  },
    { label: 'Rejected',  value: rejected,  icon: <XCircle size={12} />,   color: 'var(--rose-400)',   glow: 'rgba(244,63,94,0.15)'  },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
      {stats.map(s => (
        <div
          key={s.label}
          style={{
            background: 'rgba(13, 22, 41, 0.6)',
            border: '1px solid rgba(139,92,246,0.1)',
            borderRadius: 10,
            padding: '10px 8px',
            textAlign: 'center',
            backdropFilter: 'blur(12px)',
            transition: 'all 0.2s',
            cursor: 'default',
          }}
          onMouseEnter={e => {
            ;(e.currentTarget as HTMLDivElement).style.borderColor = `${s.glow.replace('0.25', '0.4')}`
            ;(e.currentTarget as HTMLDivElement).style.boxShadow   = `0 0 16px ${s.glow}`
          }}
          onMouseLeave={e => {
            ;(e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(139,92,246,0.1)'
            ;(e.currentTarget as HTMLDivElement).style.boxShadow   = 'none'
          }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 4, color: s.color, marginBottom: 5, opacity: 0.85,
          }}>
            {s.icon}
          </div>
          <div style={{
            fontFamily: '"Space Grotesk", sans-serif',
            fontSize: '1.3rem', fontWeight: 700,
            color: s.color,
            lineHeight: 1,
            marginBottom: 3,
          }}>
            {s.value}
          </div>
          <div style={{
            fontSize: 9, fontWeight: 600, letterSpacing: '0.07em',
            textTransform: 'uppercase', color: 'var(--text-dim)',
            fontFamily: '"Space Grotesk", sans-serif',
          }}>
            {s.label}
          </div>
        </div>
      ))}
    </div>
  )
}
