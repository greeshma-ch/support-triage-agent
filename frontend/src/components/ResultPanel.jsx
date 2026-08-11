import StatusBadge from './StatusBadge'
import ConfidenceMeter from './ConfidenceMeter'

export default function ResultPanel({ result, loading, error }) {
  if (loading) {
    return (
      <div className="loading-row">
        <span className="spinner" />
        Running classifier → retriever → agent…
      </div>
    )
  }

  if (error) {
    return <div className="error-note">{error}</div>
  }

  if (!result) {
    return (
      <div className="empty-state">
        No ticket triaged yet.
        <br />
        Submit a ticket on the left to see the classifier, retrieval confidence,
        and generated response here.
      </div>
    )
  }

  return (
    <div>
      <div className="result-header">
        <StatusBadge status={result.status} />
        <ConfidenceMeter value={result.confidence} />
      </div>

      {result.escalation_reason && (
        <div className="escalation-note">Escalated: {result.escalation_reason}</div>
      )}

      <div className="field-block" style={{ marginTop: 18 }}>
        <div className="fk">Response</div>
        <div className="fv">{result.response}</div>
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <div className="field-block">
          <div className="fk">Product area</div>
          <span className="tag">{result.product_area}</span>
        </div>
        <div className="field-block">
          <div className="fk">Request type</div>
          <span className="tag">{result.request_type}</span>
        </div>
        <div className="field-block">
          <div className="fk">Corpus</div>
          <span className="tag">{result.company || 'unknown'}</span>
        </div>
      </div>

      <div className="field-block">
        <div className="fk">Justification</div>
        <div className="fv mono" style={{ color: 'var(--text-dim)', fontSize: 12.5 }}>
          {result.justification}
        </div>
      </div>

      {result.retrieved_sources?.length > 0 && (
        <div className="field-block">
          <div className="fk">Retrieved sources</div>
          <div className="sources-list">
            {result.retrieved_sources.map((s, i) => (
              <div className="source-row" key={i}>
                <span className="path">{s.filepath}</span>
                <span>{s.source}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
