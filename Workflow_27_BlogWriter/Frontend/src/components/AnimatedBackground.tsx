import { useEffect, useRef } from 'react'

// ── Types ────────────────────────────────────────────────────────
type ShapeType = 'circle' | 'triangle' | 'square' | 'diamond' | 'star' | 'hexagon' | 'cross'

interface Particle {
  x: number; y: number
  vx: number; vy: number
  size: number        // base size
  shape: ShapeType
  color: string
  alpha: number
  angle: number       // current rotation
  rotSpeed: number    // rotation speed
  pulse: number
  pulseSpeed: number
  layer: number       // 0=slow-bg, 1=mid, 2=fast-fg
}

// ── Color palette ────────────────────────────────────────────────
const PALETTE = [
  '#8b5cf6', '#a78bfa', '#c4b5fd',  // violets
  '#06b6d4', '#22d3ee', '#67e8f9',  // cyans
  '#f59e0b', '#fbbf24', '#fcd34d',  // ambers
  '#10b981', '#34d399',             // emeralds
  '#f43f5e', '#fb7185',             // roses
  '#e879f9', '#d946ef',             // fuschias
  '#38bdf8', '#7dd3fc',             // sky blues
]

const SHAPES: ShapeType[] = ['circle', 'triangle', 'square', 'diamond', 'star', 'hexagon', 'cross']

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `${r}, ${g}, ${b}`
}

// ── Shape drawing ────────────────────────────────────────────────
function drawShape(
  ctx: CanvasRenderingContext2D,
  shape: ShapeType,
  x: number, y: number,
  size: number,
  angle: number
) {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)

  ctx.beginPath()
  switch (shape) {
    case 'circle':
      ctx.arc(0, 0, size, 0, Math.PI * 2)
      break

    case 'triangle': {
      const h = size * 1.6
      ctx.moveTo(0, -h * 0.6)
      ctx.lineTo(h * 0.55, h * 0.4)
      ctx.lineTo(-h * 0.55, h * 0.4)
      ctx.closePath()
      break
    }

    case 'square':
      ctx.rect(-size, -size, size * 2, size * 2)
      break

    case 'diamond':
      ctx.moveTo(0, -size * 1.5)
      ctx.lineTo(size, 0)
      ctx.lineTo(0, size * 1.5)
      ctx.lineTo(-size, 0)
      ctx.closePath()
      break

    case 'star': {
      const outer = size * 1.4
      const inner = size * 0.55
      const pts = 5
      for (let i = 0; i < pts * 2; i++) {
        const r2 = i % 2 === 0 ? outer : inner
        const a = (i * Math.PI) / pts - Math.PI / 2
        if (i === 0) ctx.moveTo(Math.cos(a) * r2, Math.sin(a) * r2)
        else         ctx.lineTo(Math.cos(a) * r2, Math.sin(a) * r2)
      }
      ctx.closePath()
      break
    }

    case 'hexagon': {
      for (let i = 0; i < 6; i++) {
        const a = (Math.PI / 3) * i
        const px = Math.cos(a) * size * 1.2
        const py = Math.sin(a) * size * 1.2
        if (i === 0) ctx.moveTo(px, py)
        else         ctx.lineTo(px, py)
      }
      ctx.closePath()
      break
    }

    case 'cross': {
      const arm = size * 0.4
      const len = size * 1.4
      ctx.moveTo(-arm, -len); ctx.lineTo(arm, -len)
      ctx.lineTo(arm, -arm); ctx.lineTo(len, -arm)
      ctx.lineTo(len, arm);  ctx.lineTo(arm, arm)
      ctx.lineTo(arm, len);  ctx.lineTo(-arm, len)
      ctx.lineTo(-arm, arm); ctx.lineTo(-len, arm)
      ctx.lineTo(-len, -arm); ctx.lineTo(-arm, -arm)
      ctx.closePath()
      break
    }
  }

  ctx.restore()
}

// ── Component ────────────────────────────────────────────────────
export default function AnimatedBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mouse     = useRef({ x: -9999, y: -9999, active: false })

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx    = canvas.getContext('2d')!
    let animId: number
    let particles: Particle[] = []
    let W = 0, H = 0

    // ── Resize ──────────────────────────────────────────────────
    function resize() {
      W = canvas.width  = window.innerWidth
      H = canvas.height = window.innerHeight
    }

    // ── Spawn one particle ───────────────────────────────────────
    function spawn(fromEdge = false): Particle {
      const layer = Math.random() < 0.45 ? 0 : Math.random() < 0.6 ? 1 : 2

      // Speed — layer 0 slowest, layer 2 fastest; never zero
      const baseSpd = 0.25 + layer * 0.28
      const angle   = Math.random() * Math.PI * 2
      const spd     = baseSpd + Math.random() * baseSpd

      // Size variety: small to large with bias toward small
      const sizeMin = layer === 0 ? 1   : layer === 1 ? 1.5  : 2
      const sizeMax = layer === 0 ? 4   : layer === 1 ? 7    : 11
      const size    = sizeMin + Math.pow(Math.random(), 1.8) * (sizeMax - sizeMin)

      const color = PALETTE[Math.floor(Math.random() * PALETTE.length)]

      // Spawn position — spread across whole canvas
      let x = Math.random() * W
      let y = Math.random() * H
      if (fromEdge) {
        const edge = Math.floor(Math.random() * 4)
        if (edge === 0) { x = Math.random() * W; y = -size * 2 }
        else if (edge === 1) { x = W + size * 2; y = Math.random() * H }
        else if (edge === 2) { x = Math.random() * W; y = H + size * 2 }
        else { x = -size * 2; y = Math.random() * H }
      }

      return {
        x, y,
        vx: Math.cos(angle) * spd,
        vy: Math.sin(angle) * spd,
        size,
        shape: SHAPES[Math.floor(Math.random() * SHAPES.length)],
        color,
        alpha: 0.25 + Math.random() * 0.55,
        angle: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.018 * (3 - layer),
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.012 + Math.random() * 0.025,
        layer,
      }
    }

    // ── Build initial field ──────────────────────────────────────
    function build() {
      particles = []
      const count = Math.min(Math.floor(W * H / 7500), 200)
      for (let i = 0; i < count; i++) particles.push(spawn(false))
    }

    // ── Draw nebula backdrop ─────────────────────────────────────
    function drawNebulae() {
      const blobs = [
        { x: W * 0.12, y: H * 0.18, r: 320, color: '#3b0764' },
        { x: W * 0.82, y: H * 0.78, r: 360, color: '#0c4a6e' },
        { x: W * 0.48, y: H * 0.55, r: 260, color: '#1e1b4b' },
        { x: W * 0.88, y: H * 0.12, r: 200, color: '#4a1d96' },
        { x: W * 0.08, y: H * 0.82, r: 240, color: '#064e3b' },
        { x: W * 0.55, y: H * 0.1,  r: 180, color: '#7c2d12' },
      ]
      for (const b of blobs) {
        const g   = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r)
        const rgb = hexToRgb(b.color)
        g.addColorStop(0,   `rgba(${rgb}, 0.07)`)
        g.addColorStop(0.5, `rgba(${rgb}, 0.03)`)
        g.addColorStop(1,   `rgba(${rgb}, 0)`)
        ctx.globalAlpha = 1
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    // ── Main loop ────────────────────────────────────────────────
    function draw() {
      const mx = mouse.current.x
      const my = mouse.current.y

      // Soft trail / fade
      ctx.globalAlpha = 1
      ctx.fillStyle   = 'rgba(3, 7, 18, 0.16)'
      ctx.fillRect(0, 0, W, H)

      const N = particles.length

      // ── Phase 1: Physics ──────────────────────────────────────
      for (let i = 0; i < N; i++) {
        const p = particles[i]

        // Pulse
        p.pulse += p.pulseSpeed
        p.angle += p.rotSpeed

        // ── Mouse repulsion ─────────────────────────────────
        const mdx  = p.x - mx
        const mdy  = p.y - my
        const md   = Math.sqrt(mdx * mdx + mdy * mdy)
        const mRad = 160 + p.layer * 35
        if (md < mRad && md > 0.5) {
          const f = Math.pow((mRad - md) / mRad, 1.8) * 1.8
          p.vx += (mdx / md) * f
          p.vy += (mdy / md) * f
        }

        // ── Inter-particle repulsion ────────────────────────
        const repR = 28 + p.size * 3
        for (let j = i + 1; j < N; j++) {
          const q   = particles[j]
          const ddx = p.x - q.x
          const ddy = p.y - q.y
          const d2  = ddx * ddx + ddy * ddy
          const rep = repR + q.size * 3
          if (d2 < rep * rep && d2 > 0.01) {
            const d = Math.sqrt(d2)
            const f = ((rep - d) / rep) * 0.12
            const fx = (ddx / d) * f
            const fy = (ddy / d) * f
            p.vx += fx; p.vy += fy
            q.vx -= fx; q.vy -= fy
          }
        }

        // NO center drift — removed entirely

        // Friction — very gentle to keep motion alive
        p.vx *= 0.992
        p.vy *= 0.992

        // Speed floor — prevents particles from stopping
        const spd = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
        const minSpd = 0.12 + p.layer * 0.1
        const maxSpd = 1.4 + p.layer * 0.8
        if (spd < minSpd && spd > 0) {
          p.vx = (p.vx / spd) * minSpd
          p.vy = (p.vy / spd) * minSpd
        }
        // Speed cap
        if (spd > maxSpd) {
          p.vx = (p.vx / spd) * maxSpd
          p.vy = (p.vy / spd) * maxSpd
        }

        p.x += p.vx
        p.y += p.vy

        // Wrap at edges (seamless)
        if (p.x < -30)    p.x = W + 30
        if (p.x > W + 30) p.x = -30
        if (p.y < -30)    p.y = H + 30
        if (p.y > H + 30) p.y = -30
      }

      // ── Phase 2: Draw connections ─────────────────────────────
      for (let i = 0; i < N; i++) {
        const p      = particles[i]
        const rgb    = hexToRgb(p.color)
        const connR  = 70 + p.layer * 25 + p.size * 3

        for (let j = i + 1; j < N; j++) {
          const q   = particles[j]
          if (Math.abs(p.layer - q.layer) > 1) continue
          const ddx = p.x - q.x
          const ddy = p.y - q.y
          const d   = Math.sqrt(ddx * ddx + ddy * ddy)
          if (d < connR) {
            const t = 1 - d / connR
            ctx.beginPath()
            ctx.globalAlpha = t * t * 0.22 * Math.min(p.alpha, q.alpha)
            ctx.strokeStyle = `rgba(${rgb}, 1)`
            ctx.lineWidth   = t * 1.1
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(q.x, q.y)
            ctx.stroke()
          }
        }
      }

      // ── Phase 3: Draw shapes ──────────────────────────────────
      for (let i = 0; i < N; i++) {
        const p   = particles[i]
        const rgb = hexToRgb(p.color)
        const r   = p.size + Math.sin(p.pulse) * p.size * 0.25

        // Outer glow halo
        const gRad = r * 6
        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, gRad)
        glow.addColorStop(0,   `rgba(${rgb}, ${p.alpha * 0.45})`)
        glow.addColorStop(0.4, `rgba(${rgb}, ${p.alpha * 0.1})`)
        glow.addColorStop(1,   `rgba(${rgb}, 0)`)
        ctx.globalAlpha = 1
        ctx.fillStyle   = glow
        ctx.beginPath()
        ctx.arc(p.x, p.y, gRad, 0, Math.PI * 2)
        ctx.fill()

        // Core shape
        ctx.globalAlpha = p.alpha
        ctx.fillStyle   = `rgba(${rgb}, 1)`
        drawShape(ctx, p.shape, p.x, p.y, r, p.angle)
        ctx.fill()

        // Bright center highlight
        ctx.globalAlpha = p.alpha * 0.7
        ctx.fillStyle   = `rgba(255, 255, 255, 0.55)`
        ctx.beginPath()
        ctx.arc(p.x - r * 0.25, p.y - r * 0.25, r * 0.28, 0, Math.PI * 2)
        ctx.fill()
      }

      ctx.globalAlpha = 1
      animId = requestAnimationFrame(draw)
    }

    // ── Boot ─────────────────────────────────────────────────────
    resize()
    build()
    drawNebulae()
    draw()

    // ── Events ───────────────────────────────────────────────────
    const onMove  = (e: MouseEvent) => {
      mouse.current.x = e.clientX
      mouse.current.y = e.clientY
      mouse.current.active = true
    }
    const onLeave  = () => { mouse.current.active = false; mouse.current.x = -9999; mouse.current.y = -9999 }
    const onResize = () => { resize(); build(); drawNebulae() }

    window.addEventListener('mousemove',  onMove)
    window.addEventListener('mouseleave', onLeave)
    window.addEventListener('resize',     onResize)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('mousemove',  onMove)
      window.removeEventListener('mouseleave', onLeave)
      window.removeEventListener('resize',     onResize)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        background: 'linear-gradient(135deg, #030712 0%, #06091a 40%, #060d1f 70%, #0a0f23 100%)',
      }}
    />
  )
}
