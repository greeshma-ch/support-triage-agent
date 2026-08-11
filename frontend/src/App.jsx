import { useEffect, useState, useCallback } from 'react'
import TicketForm from './components/TicketForm'
import ResultPanel from './components/ResultPanel'
import CorpusManager from './components/CorpusManager'
import { fetchCompanies, triageTicket } from './api'

export default function App() {
  const [companies, setCompanies] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const loadCompanies = useCallback(() => {
    fetchCompanies()
      .then((r) => setCompanies(r.companies || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    loadCompanies()
  }, [loadCompanies])

  async function handleSubmit({ subject, issue, company }) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await triageTicket({ subject, issue, company })
      setResult(res)
    } catch (e) {
      setError(e.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="console">
      <header className="console-header">
        <div className="brand">
          <span className="brand-dot" />
          <h1>Triage Console</h1>
          <span className="sub">multi-domain support agent</span>
        </div>
        <div className="meta">{companies.length} corpora indexed</div>
      </header>

      <div className="grid">
        <div>
          <div className="panel">
            <div className="panel-label">Submit ticket</div>
            <TicketForm companies={companies} onSubmit={handleSubmit} loading={loading} />
          </div>

          <div className="panel">
            <div className="panel-label">
              Corpus manager <span className="count">{companies.length} active</span>
            </div>
            <CorpusManager companies={companies} onChanged={loadCompanies} />
          </div>
        </div>

        <div className="panel">
          <div className="panel-label">Triage result</div>
          <ResultPanel result={result} loading={loading} error={error} />
        </div>
      </div>
    </div>
  )
}
