import { useState, useCallback } from 'react'
import { Zap, Sparkles } from 'lucide-react'

import AnimatedBackground from './components/AnimatedBackground'
import GenerateForm        from './components/GenerateForm'
import BlogList            from './components/BlogList'
import BlogViewer          from './components/BlogViewer'
import StatsBar            from './components/StatsBar'

import type { Blog } from './types'

export default function App() {
  const [selected,   setSelected]   = useState<Blog | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  function handleGenerated(blog: Partial<Blog> & { thread_id: string }) {
    refresh()
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

      <div style={{
        position: 'relative', zIndex: 1,
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
      }}>

        {/* ── Header ────────────────────────────────────────── */}
        <header style={{
          borderBottom: '1px solid rgba(139, 92, 246, 0.12)',
          background: 'rgba(3, 7, 18, 0.6)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          padding: '0 32px',
          height: 60,
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          position: 'sticky', top: 0, zIndex: 50,
        }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34, height: 34,
              background: 'linear-gradient(135deg, rgba(139,92,246,0.25), rgba(6,182,212,0.15))',
              border: '1px solid rgba(139,92,246,0.35)',
              borderRadius: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 16px rgba(139,92,246,0.2)',
            }}>
              <Zap size={16} color="#a78bfa" fill="rgba(139,92,246,0.3)" />
            </div>
            <div style={{ lineHeight: 1.1 }}>
              <div style={{
                fontFamily: '"Space Grotesk", sans-serif',
                fontSize: '1.15rem', fontWeight: 700,
                letterSpacing: '-0.02em',
              }}>
                <span style={{ color: '#e2e8f8' }}>Blog</span>
                <span className="text-gradient-violet">Forge</span>
              </div>
              <div style={{
                fontSize: 9, fontWeight: 600, letterSpacing: '0.12em',
                textTransform: 'uppercase', color: 'var(--text-dim)',
                fontFamily: '"Space Grotesk", sans-serif',
              }}>
                AI · HITL
              </div>
            </div>
          </div>

          {/* Glow separator */}
          <div style={{
            width: 1, height: 28,
            background: 'linear-gradient(180deg, transparent, rgba(139,92,246,0.3), transparent)',
          }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'var(--emerald)',
              boxShadow: '0 0 8px var(--emerald)',
              animation: 'dotBlink 2.5s ease-in-out infinite',
            }} />
            <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: '"Space Grotesk", sans-serif', letterSpacing: '0.04em' }}>
              System Online
            </span>
          </div>

          <div style={{ flex: 1 }} />

          {/* Breadcrumb */}
          {selected && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(139,92,246,0.06)',
              border: '1px solid rgba(139,92,246,0.15)',
              borderRadius: 8, padding: '5px 12px',
            }}>
              <span
                style={{ cursor: 'pointer', color: 'var(--violet-400)', fontSize: 12, fontWeight: 500 }}
                onClick={() => setSelected(null)}
              >
                Dashboard
              </span>
              <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>›</span>
              <span style={{
                maxWidth: 200, overflow: 'hidden',
                textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                color: 'var(--text-mid)', fontSize: 12,
              }}>
                {selected.blog_title || selected.topic}
              </span>
            </div>
          )}
        </header>

        {/* ── Main ──────────────────────────────────────────── */}
        <main style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: selected ? '300px 1fr' : '330px 1fr',
          gap: 0,
          maxWidth: 1440,
          width: '100%',
          margin: '0 auto',
          padding: '20px 20px',
          alignItems: 'start',
        }}>

          {/* ── Sidebar ───────────────────────────────────────── */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 16,
            paddingRight: 20,
            borderRight: '1px solid rgba(139,92,246,0.08)',
            position: 'sticky', top: 80,
            maxHeight: 'calc(100vh - 100px)',
            overflowY: 'auto',
            overflowX: 'hidden',
          }}>
            <GenerateForm onGenerated={handleGenerated} />

            {/* Library header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              paddingLeft: 2,
            }}>
              <span style={{
                fontSize: 10, fontWeight: 700, color: 'var(--text-dim)',
                letterSpacing: '0.1em', textTransform: 'uppercase',
                fontFamily: '"Space Grotesk", sans-serif',
              }}>
                Blog Library
              </span>
              <div style={{
                height: 1, flex: 1, margin: '0 10px',
                background: 'linear-gradient(90deg, rgba(139,92,246,0.25), transparent)',
              }} />
            </div>

            <StatsBar refreshKey={refreshKey} />

            <BlogList onSelect={setSelected} refreshKey={refreshKey} />
          </div>

          {/* ── Content panel ─────────────────────────────────── */}
          <div style={{ paddingLeft: 24, minHeight: 'calc(100vh - 100px)' }}>
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

        {/* ── Footer ────────────────────────────────────────── */}
        <footer style={{
          borderTop: '1px solid rgba(139,92,246,0.08)',
          padding: '10px 32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
        }}>
          <span style={{ fontSize: 11, color: 'var(--text-ghost)', fontFamily: '"Space Grotesk", sans-serif', letterSpacing: '0.04em' }}>
            BlogForge
          </span>
          <span style={{ color: 'rgba(139,92,246,0.3)', fontSize: 11 }}>·</span>
          <span style={{ fontSize: 11, color: 'var(--text-ghost)' }}>AI-powered · Human-approved</span>
        </footer>
      </div>
    </>
  )
}

function EmptyState() {
  const tips = [
    { icon: '✦', text: 'AI writes the full blog — you review and approve' },
    { icon: '✦', text: 'Published blogs render in-app with full styling' },
    { icon: '✦', text: 'Download as Markdown, PDF or Word' },
  ]

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      minHeight: '70vh', gap: 28, textAlign: 'center',
    }}
    className="animate-fade-in">

      {/* Animated icon */}
      <div style={{ position: 'relative' }}>
        <div style={{
          width: 88, height: 88,
          background: 'radial-gradient(circle, rgba(139,92,246,0.15), rgba(6,182,212,0.05))',
          border: '1px solid rgba(139,92,246,0.2)',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 36,
        }}
        className="animate-float animate-pulse-glow"
        >
          ✍️
        </div>
        {/* Orbiting sparkle */}
        <div style={{
          position: 'absolute', top: 4, right: 4,
          width: 22, height: 22,
          background: 'linear-gradient(135deg, rgba(139,92,246,0.3), rgba(6,182,212,0.2))',
          border: '1px solid rgba(139,92,246,0.4)',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Sparkles size={10} color="#a78bfa" />
        </div>
      </div>

      <div>
        <h2 style={{
          fontFamily: '"Space Grotesk", sans-serif',
          fontSize: '1.6rem', fontWeight: 700,
          margin: '0 0 8px',
          lineHeight: 1.2,
        }}>
          <span className="text-gradient-violet">Select a blog</span>
          <span style={{ color: 'var(--text-mid)' }}> to read</span>
        </h2>
        <p style={{ color: 'var(--text-dim)', margin: 0, fontSize: 14, fontWeight: 400 }}>
          Pick one from the library — or generate a new one on the left.
        </p>
      </div>

      {/* Tips */}
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 8,
        maxWidth: 340,
      }}>
        {tips.map((t, i) => (
          <div
            key={i}
            className="animate-slide-up"
            style={{
              animationDelay: `${i * 60}ms`,
              fontSize: 12.5, color: 'var(--text-dim)',
              background: 'rgba(139,92,246,0.04)',
              border: '1px solid rgba(139,92,246,0.1)',
              borderRadius: 10, padding: '9px 16px',
              textAlign: 'left',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
            <span style={{ color: 'var(--violet-400)', fontSize: 10 }}>{t.icon}</span>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
