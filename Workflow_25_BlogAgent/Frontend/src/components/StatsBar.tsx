import { useEffect, useState } from 'react'
import { BookOpen, Clock, CheckCircle, XCircle } from 'lucide-react'
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
  const published = blogs.filter(b => b.status === 'COMPLETED').length
  const rejected  = blogs.filter(b => b.status === 'REJECTED').length

  const stats = [
    { label: 'Total',     value: total,     icon: <BookOpen size={14} />,    color: '#9fb3c8' },
    { label: 'Pending',   value: pending,   icon: <Clock size={14} />,       color: '#fbbf24' },
    { label: 'Published', value: published, icon: <CheckCircle size={14} />, color: '#34d399' },
    { label: 'Rejected',  value: rejected,  icon: <XCircle size={14} />,     color: '#fb7185' },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 10,
    }}>
      {stats.map(s => (
        <div
          key={s.label}
          className="card"
          style={{ padding: '12px 16px', textAlign: 'center' }}
        >
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 6, color: s.color, marginBottom: 4,
          }}>
            {s.icon}
            <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {s.label}
            </span>
          </div>
          <div style={{
            fontFamily: '"Playfair Display", serif',
            fontSize: '1.5rem', fontWeight: 700,
            color: s.color,
          }}>
            {s.value}
          </div>
        </div>
      ))}
    </div>
  )
}
