import { useState, useRef, useEffect } from 'react'
import { Download, FileText, File, FileCode, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'
import { downloadBlog } from '../hooks/useDownload'
import type { DownloadFormat } from '../types'

interface Props {
  content: string
  title: string
}

const FORMATS: { label: string; value: DownloadFormat; icon: React.ReactNode; ext: string; color: string }[] = [
  { label: 'Markdown',  value: 'markdown', icon: <FileCode size={13} />,  ext: '.md',   color: 'var(--cyan-400)' },
  { label: 'PDF',       value: 'pdf',      icon: <File size={13} />,      ext: '.pdf',  color: 'var(--rose-400)' },
  { label: 'Word DOCX', value: 'docx',     icon: <FileText size={13} />,  ext: '.docx', color: 'var(--violet-400)' },
]

export default function DownloadMenu({ content, title }: Props) {
  const [open,    setOpen]    = useState(false)
  const [loading, setLoading] = useState<DownloadFormat | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  async function handle(fmt: DownloadFormat) {
    setLoading(fmt)
    try {
      await downloadBlog(content, title, fmt)
      toast.success(`Downloaded as ${fmt.toUpperCase()}`)
    } catch (err: any) {
      toast.error('Download failed: ' + err.message)
    } finally {
      setLoading(null)
      setOpen(false)
    }
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        className="btn btn-ghost"
        onClick={() => setOpen(o => !o)}
        style={{ gap: 5, fontSize: 12 }}
      >
        <Download size={12} />
        Download
        <ChevronDown size={10} style={{
          transition: 'transform 0.2s',
          transform: open ? 'rotate(180deg)' : 'none',
        }} />
      </button>

      {open && (
        <div
          className="animate-scale-in"
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 8px)',
            background: 'rgba(10, 18, 34, 0.97)',
            border: '1px solid rgba(139,92,246,0.2)',
            borderRadius: 12,
            padding: '6px',
            zIndex: 60,
            minWidth: 190,
            boxShadow: '0 24px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(139,92,246,0.08), var(--shadow-glow)',
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Header */}
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
            color: 'var(--text-ghost)', textTransform: 'uppercase',
            fontFamily: '"Space Grotesk", sans-serif',
            padding: '4px 10px 8px',
            borderBottom: '1px solid rgba(139,92,246,0.08)',
            marginBottom: 4,
          }}>
            Export Format
          </div>

          {FORMATS.map(f => (
            <button
              key={f.value}
              onClick={() => handle(f.value)}
              disabled={!!loading}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                width: '100%',
                background: loading === f.value ? 'rgba(139,92,246,0.08)' : 'transparent',
                border: 'none',
                borderRadius: 8, padding: '9px 12px',
                cursor: loading ? 'wait' : 'pointer',
                color: loading === f.value ? f.color : 'var(--text-mid)',
                fontSize: 13,
                fontFamily: '"Inter", sans-serif',
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => {
                if (!loading) {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(139,92,246,0.08)'
                  ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-bright)'
                }
              }}
              onMouseLeave={e => {
                if (!loading) {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-mid)'
                }
              }}
            >
              {loading === f.value
                ? <div className="spinner" style={{ width: 13, height: 13, flexShrink: 0 }} />
                : <span style={{ color: f.color }}>{f.icon}</span>
              }
              <span style={{ flex: 1, textAlign: 'left', fontWeight: 500 }}>{f.label}</span>
              <span style={{
                fontSize: 10, color: 'var(--text-ghost)',
                background: 'rgba(139,92,246,0.06)',
                border: '1px solid rgba(139,92,246,0.1)',
                borderRadius: 4, padding: '1px 6px',
                fontFamily: '"Fira Code", monospace',
              }}>
                {f.ext}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
