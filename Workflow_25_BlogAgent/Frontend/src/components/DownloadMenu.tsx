import { useState, useRef, useEffect } from 'react'
import { Download, FileText, File, FileCode } from 'lucide-react'
import toast from 'react-hot-toast'
import { downloadBlog } from '../hooks/useDownload'
import type { DownloadFormat } from '../types'

interface Props {
  content: string
  title: string
}

const formats: { label: string; value: DownloadFormat; icon: React.ReactNode; ext: string }[] = [
  { label: 'Markdown',     value: 'markdown', icon: <FileCode size={14} />,  ext: '.md'   },
  { label: 'PDF Document', value: 'pdf',      icon: <File size={14} />,      ext: '.pdf'  },
  { label: 'Word (DOCX)',  value: 'docx',     icon: <FileText size={14} />,  ext: '.docx' },
]

export default function DownloadMenu({ content, title }: Props) {
  const [open, setOpen]       = useState(false)
  const [loading, setLoading] = useState<DownloadFormat | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
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
        style={{ gap: 6 }}
      >
        <Download size={14} />
        Download
      </button>

      {open && (
        <div
          className="animate-slide-up"
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 6px)',
            background: '#132844',
            border: '1px solid rgba(251,191,36,0.2)',
            borderRadius: 10,
            padding: '6px',
            zIndex: 50,
            minWidth: 180,
            boxShadow: '0 16px 40px rgba(0,0,0,0.5)',
          }}
        >
          {formats.map(f => (
            <button
              key={f.value}
              onClick={() => handle(f.value)}
              disabled={loading === f.value}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                background: 'transparent',
                border: 'none',
                borderRadius: 7,
                padding: '8px 12px',
                cursor: 'pointer',
                color: loading === f.value ? '#fbbf24' : '#9fb3c8',
                fontSize: 13,
                fontFamily: '"DM Sans", sans-serif',
                transition: 'background 0.15s, color 0.15s',
              }}
              onMouseEnter={e => {
                if (loading !== f.value) {
                  ;(e.currentTarget as HTMLButtonElement).style.background =
                    'rgba(251,191,36,0.08)'
                  ;(e.currentTarget as HTMLButtonElement).style.color = '#e8edf2'
                }
              }}
              onMouseLeave={e => {
                if (loading !== f.value) {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  ;(e.currentTarget as HTMLButtonElement).style.color = '#9fb3c8'
                }
              }}
            >
              {loading === f.value ? (
                <div className="spinner" style={{ width: 14, height: 14, flexShrink: 0 }} />
              ) : (
                f.icon
              )}
              <span style={{ flex: 1, textAlign: 'left' }}>{f.label}</span>
              <span style={{ fontSize: 11, color: '#486581' }}>{f.ext}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
