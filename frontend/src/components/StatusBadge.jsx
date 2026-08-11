export default function StatusBadge({ status }) {
  const isReplied = status === 'replied'
  return (
    <span className={`status-badge ${isReplied ? 'status-replied' : 'status-escalated'}`}>
      <span className="light" />
      {isReplied ? 'Replied' : 'Escalated'}
    </span>
  )
}
