export default function ConfidenceMeter({ value }) {
  const pct = Math.round(value * 100)
  const litBars = Math.max(1, Math.round(value * 5))

  let color = '#4dd9b0' // teal - strong
  if (value < 0.35) color = '#e8646b' // red - weak
  else if (value < 0.6) color = '#f2b84b' // amber - moderate

  return (
    <div className="confidence-meter">
      <div className="confidence-bars" style={{ '--sig-color': color }}>
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className={`bar ${i < litBars ? 'on' : ''}`} />
        ))}
      </div>
      <div>
        <div className="confidence-value" style={{ color }}>
          {pct}%
        </div>
        <div className="confidence-label">grounding signal</div>
      </div>
    </div>
  )
}
