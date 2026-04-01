import { useState, useCallback } from 'react'
import { Feather } from 'lucide-react'

import AnimatedBackground from './components/AnimatedBackground'
import GenerateForm        from './components/GenerateForm'
import BlogList            from './components/BlogList'
import BlogViewer          from './components/BlogViewer'
import StatsBar            from './components/StatsBar'

import type { Blog } from './types'

export default function App() {
  const [selected,    setSelected]    = useState<Blog | null>(null)
  const [refreshKey,  setRefreshKey]  = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  function handleGenerated(blog: Partial<Blog> & { thread_id: string }) {
    refresh()
    // Immediately open the new blog in viewer
    setSelected(blog as Blog)
  }

  function handleBack() {
    setSelected(null)
    refresh()
  }

  function handleUpdated(updated: Blog) {
    setSelected(updated)
    refresh()
  }

  return (
    <>
      <AnimatedBackground />

      {/* Shell */}
      <div style={{
        position: 'relative', zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
      }}>

        {/* ── Header ── */}
        <header style={{
          borderBottom: '1px solid rgba(251,191,36,0.1)',
          background: 'rgba(6,14,26,0.7)',
          backdropFilter: 'blur(12px)',
          padding: '14px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          position: 'sticky', top: 0, zIndex: 10,
        }}>
          <div style={{
            width: 36, height: 36,
            background: 'rgba(251,191,36,0.12)',
            border: '1px solid rgba(251,191,36,0.3)',
            borderRadius: 9,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Feather size={17} color="#fbbf24" />
          </div>
          <div>
            <span style={{
              fontFamily: '"Playfair Display", serif',
              fontSize: '1.25rem', fontWeight: 700,
              color: '#e8edf2',
              letterSpacing: '-0.01em',
            }}>
              Blog<span style={{ color: '#fbbf24' }}>Forge</span>
            </span>
            <span style={{
              marginLeft: 10, fontSize: 11, color: '#486581',
              fontWeight: 500, letterSpacing: '0.06em', textTransform: 'uppercase',
            }}>
              AI · HITL
            </span>
          </div>

          <div style={{ flex: 1 }} />

          {/* Breadcrumb */}
          {selected && (
            <div style={{
              fontSize: 12, color: '#627d98',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <span
                style={{ cursor: 'pointer', color: '#fbbf24' }}
                onClick={() => setSelected(null)}
              >
                Dashboard
              </span>
              <span>/</span>
              <span style={{
                maxWidth: 220, overflow: 'hidden',
                textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                color: '#9fb3c8',
              }}>
                {selected.blog_title || selected.topic}
              </span>
            </div>
          )}
        </header>

        {/* ── Main ── */}
        <main style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: selected ? '320px 1fr' : '360px 1fr',
          gap: 0,
          maxWidth: 1400,
          width: '100%',
          margin: '0 auto',
          padding: '24px 24px',
          alignItems: 'start',
        }}>

          {/* ── Left sidebar ── */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 20,
            paddingRight: 24,
            borderRight: '1px solid rgba(251,191,36,0.07)',
            position: 'sticky', top: 86,
            maxHeight: 'calc(100vh - 110px)',
            overflowY: 'auto',
          }}>
            <GenerateForm onGenerated={handleGenerated} />

            <div>
              <div style={{
                fontSize: 11, fontWeight: 600, color: '#486581',
                letterSpacing: '0.07em', textTransform: 'uppercase',
                marginBottom: 12, paddingLeft: 2,
              }}>
                Blog Library
              </div>
              <StatsBar refreshKey={refreshKey} />
            </div>

            <BlogList
              onSelect={setSelected}
              refreshKey={refreshKey}
            />
          </div>

          {/* ── Right content ── */}
          <div style={{ paddingLeft: 28 }}>
            {selected ? (
              <BlogViewer
                blog={selected}
                onBack={handleBack}
                onDeleted={() => { setSelected(null); refresh() }}
                onUpdated={handleUpdated}
              />
            ) : (
              <EmptyState />
            )}
          </div>
        </main>

        {/* ── Footer ── */}
        <footer style={{
          borderTop: '1px solid rgba(251,191,36,0.07)',
          padding: '12px 32px',
          textAlign: 'center',
          fontSize: 11, color: '#334e68',
        }}>
          BlogForge · AI-powered blog generation with human-in-the-loop approval
        </footer>
      </div>
    </>
  )
}

function EmptyState() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      minHeight: '60vh', gap: 16, textAlign: 'center',
    }}>
      <div style={{
        width: 72, height: 72,
        background: 'rgba(251,191,36,0.06)',
        border: '1px solid rgba(251,191,36,0.15)',
        borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 30,
      }}>
        ✍️
      </div>
      <div>
        <h2 style={{
          fontFamily: '"Playfair Display", serif',
          fontSize: '1.5rem', fontWeight: 600,
          color: '#9fb3c8', margin: '0 0 6px',
        }}>
          Select a blog to read
        </h2>
        <p style={{ color: '#486581', margin: 0, fontSize: 14 }}>
          Pick one from the library, or generate a new one on the left.
        </p>
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 8,
        marginTop: 8, maxWidth: 320,
      }}>
        {[
          '✦  AI writes — you review and approve',
          '✦  Download as Markdown, PDF or DOCX',
          '✦  Edit, rename, or delete any blog',
        ].map(tip => (
          <div key={tip} style={{
            fontSize: 12, color: '#486581',
            background: 'rgba(251,191,36,0.04)',
            border: '1px solid rgba(251,191,36,0.08)',
            borderRadius: 8, padding: '7px 14px',
            textAlign: 'left',
          }}>
            {tip}
          </div>
        ))}
      </div>
    </div>
  )
}
