import type { BlogStatus } from '../types'

const cfg: Record<BlogStatus, { label: string; dot: string; cls: string }> = {
  PENDING:  { label: 'Pending Review', dot: '#fbbf24', cls: 'badge-pending'  },
  APPROVED: { label: 'Published',      dot: '#10b981', cls: 'badge-approved' },
  REJECTED: { label: 'Rejected',       dot: '#f43f5e', cls: 'badge-rejected' },
}

export default function StatusBadge({ status }: { status: BlogStatus }) {
  const { label, dot, cls } = cfg[status] ?? { label: status, dot: '#4a5a72', cls: '' }
  return (
    <span className={`badge ${cls}`}>
      <span style={{
        width: 5, height: 5,
        borderRadius: '50%',
        background: dot,
        display: 'inline-block',
        flexShrink: 0,
        boxShadow: `0 0 5px ${dot}`,
      }} />
      {label}
    </span>
  )
}
