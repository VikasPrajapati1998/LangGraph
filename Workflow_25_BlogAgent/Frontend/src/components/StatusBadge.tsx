import type { BlogStatus } from '../types'

const cfg: Record<BlogStatus, { label: string; dot: string }> = {
  PENDING:   { label: 'Pending Review', dot: '#fbbf24' },
  APPROVED:  { label: 'Approved',       dot: '#34d399' },
  COMPLETED: { label: 'Published',      dot: '#34d399' },
  REJECTED:  { label: 'Rejected',       dot: '#fb7185' },
  FAILED:    { label: 'Failed',         dot: '#fb7185' },
}

export default function StatusBadge({ status }: { status: BlogStatus }) {
  const { label, dot } = cfg[status] ?? { label: status, dot: '#627d98' }
  const cls = `badge badge-${status.toLowerCase()}`
  return (
    <span className={cls}>
      <span style={{
        width: 6, height: 6,
        borderRadius: '50%',
        background: dot,
        display: 'inline-block',
        flexShrink: 0,
      }} />
      {label}
    </span>
  )
}
