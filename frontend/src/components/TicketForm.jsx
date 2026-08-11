import { useState } from 'react'

export default function TicketForm({ companies, onSubmit, loading }) {
  const [subject, setSubject] = useState('')
  const [issue, setIssue] = useState('')
  const [company, setCompany] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!issue.trim()) return
    onSubmit({ subject, issue, company })
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="subject">Subject</label>
      <input
        id="subject"
        type="text"
        placeholder="e.g. Can't access my account"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
      />

      <label htmlFor="company">Corpus</label>
      <select id="company" value={company} onChange={(e) => setCompany(e.target.value)}>
        <option value="">Auto-detect</option>
        {companies.map((c) => (
          <option key={c.name} value={c.name}>
            {c.name} ({c.chunk_count} chunks)
          </option>
        ))}
      </select>

      <label htmlFor="issue">Ticket body</label>
      <textarea
        id="issue"
        placeholder="Paste the full support ticket text here…"
        value={issue}
        onChange={(e) => setIssue(e.target.value)}
        required
      />

      <button type="submit" className="btn-primary" disabled={loading || !issue.trim()}>
        {loading ? 'Running triage…' : 'Run triage'}
      </button>
    </form>
  )
}
