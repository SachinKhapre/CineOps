import { useEffect, useRef, useState } from 'react'
import { Timeline } from './components/Timeline'
import { Findings } from './components/Findings'
import type { AgentEvent, InvestigationResult, InvestigationSummary } from './types'

const DEFAULT_QUESTION = 'Something went wrong with our streaming content yesterday. Investigate it.'

export default function App() {
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [running, setRunning] = useState(false)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [result, setResult] = useState<InvestigationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<EventSource | null>(null)

  // Don't leave a stream open if the component unmounts mid-investigation.
  useEffect(() => () => sourceRef.current?.close(), [])

  async function start() {
    setRunning(true)
    setEvents([])
    setResult(null)
    setError(null)
    sourceRef.current?.close()

    let summary: InvestigationSummary
    try {
      const response = await fetch('/api/investigations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!response.ok) throw new Error(`API returned ${response.status}`)
      summary = await response.json()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'could not reach the API')
      setRunning(false)
      return
    }

    const source = new EventSource(`/api/investigations/${summary.id}/events`)
    sourceRef.current = source

    source.onmessage = (message) => {
      const event: AgentEvent = JSON.parse(message.data)
      setEvents((previous) => [...previous, event])
      if (event.type === 'complete' || event.type === 'error') {
        if (event.result) setResult(event.result)
        else if (event.error) setError(event.error)
        source.close()
        setRunning(false)
      }
    }

    source.onerror = () => {
      // The stream also closes normally when the investigation ends; only
      // treat it as a failure if no result arrived.
      source.close()
      setRunning(false)
      setResult((current) => {
        if (!current) setError('lost connection to the investigation stream')
        return current
      })
    }
  }

  const failed = Boolean(error) || Boolean(result?.error)

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>MediaDoc</h1>
          <p className="header__tagline">Entertainment intelligence</p>
        </div>
        <span className={`status status--${running ? 'running' : failed ? 'failed' : result ? 'complete' : 'idle'}`}>
          {running ? 'Investigating' : failed ? 'Failed' : result ? 'Complete' : 'Ready'}
        </span>
      </header>

      <section className="ask">
        <label htmlFor="question">What should we investigate?</label>
        <div className="ask__row">
          <input
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !running && question.trim() && start()}
            placeholder="Something went wrong yesterday…"
            disabled={running}
          />
          <button onClick={start} disabled={running || !question.trim()}>
            {running ? 'Investigating…' : 'Investigate'}
          </button>
        </div>
      </section>

      {error && <p className="error banner">{error}</p>}

      <div className="columns">
        <Timeline events={events} failed={failed} />
        <div className="findings">
          {result ? (
            <Findings result={result} />
          ) : (
            <section className="panel">
              <h2>Findings</h2>
              <p className="muted">
                {running
                  ? 'The agent is querying ClickHouse. Findings appear here once the evidence is in.'
                  : 'Start an investigation to see the anomaly, evidence and recommendation.'}
              </p>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
