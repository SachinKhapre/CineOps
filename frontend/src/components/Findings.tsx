import type { Detection, EvidenceItem, InvestigationResult, Segment } from '../types'

const pct = (v: number) => `${(v * 100).toFixed(2)}%`

const metricLabel = (m: string) => m.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

function hours(range: [number, number] | null) {
  if (!range) return null
  const pad = (h: number) => `${String(h).padStart(2, '0')}:00`
  return `${pad(range[0])}–${pad(range[1])}`
}

/** Baseline vs observed, as two bars scaled to whichever is larger. */
function AnomalyChart({ detection }: { detection: Detection }) {
  const { value, baseline_value: baseline } = detection.most_affected
  const max = Math.max(value, baseline) || 1
  const worse = value > baseline ? 'up' : 'down'

  return (
    <div className="chart">
      <div className="chart__row">
        <span className="chart__label">Baseline</span>
        <div className="chart__track">
          <div className="chart__bar chart__bar--baseline" style={{ width: `${(baseline / max) * 100}%` }} />
        </div>
        <span className="chart__value">{pct(baseline)}</span>
      </div>
      <div className="chart__row">
        <span className="chart__label">{detection.anomaly_day}</span>
        <div className="chart__track">
          <div className={`chart__bar chart__bar--anomaly chart__bar--${worse}`} style={{ width: `${(value / max) * 100}%` }} />
        </div>
        <span className="chart__value">{pct(value)}</span>
      </div>
    </div>
  )
}

function AffectedSegment({ segment }: { segment: Segment }) {
  const chips = [
    ['Device', segment.device_type],
    ['Region', segment.region],
    ['Quality', segment.quality],
    ['Hours', hours(segment.hour_range) ?? 'all day'],
  ]
  return (
    <div className="chips">
      {chips.map(([label, value]) => (
        <div className="chip" key={label}>
          <span className="chip__label">{label}</span>
          <span className="chip__value">{value}</span>
        </div>
      ))}
    </div>
  )
}

function Confidence({ score, band }: { score: number; band: string }) {
  return (
    <div className="confidence">
      <div className="confidence__head">
        <span className={`confidence__band confidence__band--${band.toLowerCase().replace(' ', '-')}`}>{band}</span>
        <span className="confidence__score">{score}/100</span>
      </div>
      <div className="confidence__track">
        <div className="confidence__fill" style={{ width: `${score}%` }} />
      </div>
      <p className="muted small">Scored from the evidence below, not asserted by the model.</p>
    </div>
  )
}

function Evidence({ items }: { items: EvidenceItem[] }) {
  return (
    <ul className="evidence">
      {items.map((item, i) => (
        <li key={i} className={`evidence__item evidence__item--${item.supported ? 'supported' : 'rejected'}`}>
          <div className="evidence__head">
            <span className="evidence__verdict">{item.supported ? 'Supported' : 'Ruled out'}</span>
            <span className="evidence__hypothesis">{item.hypothesis}</span>
            <span className={`evidence__strength evidence__strength--${item.strength}`}>{item.strength}</span>
          </div>
          <p className="evidence__observation">{item.observation}</p>
        </li>
      ))}
    </ul>
  )
}

export function Findings({ result }: { result: InvestigationResult }) {
  const { detection, evidence, confidence, conclusion, stats } = result

  if (result.error) {
    return (
      <section className="panel">
        <h2>Investigation failed</h2>
        <p className="error">
          {result.phase ? `Phase “${result.phase}”: ` : ''}
          {result.error}
        </p>
      </section>
    )
  }

  if (!detection) return null
  const segment = detection.most_affected
  const delta = detection.delta_percent

  return (
    <>
      <section className="panel">
        <h2>Finding</h2>
        <div className="finding__headline">
          <span className="finding__metric">{metricLabel(detection.metric)}</span>
          <span className={`finding__delta finding__delta--${delta >= 0 ? 'up' : 'down'}`}>
            {delta >= 0 ? '↑' : '↓'} {Math.abs(delta).toFixed(1)}%
          </span>
        </div>
        <AnomalyChart detection={detection} />
        <h3>Affected segment</h3>
        <AffectedSegment segment={segment} />
        {detection.other_segments_checked?.length > 0 && (
          <p className="muted small">
            Compared against {detection.other_segments_checked.length} other segments.
          </p>
        )}
      </section>

      {confidence && (
        <section className="panel">
          <h2>Confidence</h2>
          <Confidence score={confidence.score} band={confidence.band} />
        </section>
      )}

      {evidence && evidence.length > 0 && (
        <section className="panel">
          <h2>Evidence</h2>
          <Evidence items={evidence} />
        </section>
      )}

      {conclusion && (
        <section className="panel">
          <h2>Conclusion</h2>
          <p className="conclusion__cause">{conclusion.root_cause}</p>
          <h3>Recommended action</h3>
          <p className="conclusion__action">{conclusion.recommendation}</p>
          {conclusion.unresolved_uncertainty && (
            <>
              <h3>Unresolved</h3>
              <p className="muted">{conclusion.unresolved_uncertainty}</p>
            </>
          )}
        </section>
      )}

      {stats && (
        <p className="stats muted small">
          {stats.queries} ClickHouse queries · {stats.model_calls} model calls · {stats.seconds}s
        </p>
      )}
    </>
  )
}
