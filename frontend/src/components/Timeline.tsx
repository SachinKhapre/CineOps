import { PHASES, type AgentEvent, type Phase } from '../types'

function clockTime(iso: string) {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour12: false })
}

type PhaseState = 'pending' | 'active' | 'done'

function phaseState(phase: Phase, events: AgentEvent[], failed: boolean): PhaseState {
  const started = events.some((e) => e.phase === phase && e.type === 'phase_start')
  const finished = events.some((e) => e.phase === phase && e.type === 'phase_complete')
  if (finished) return 'done'
  if (started) return failed ? 'done' : 'active'
  return 'pending'
}

export function Timeline({ events, failed }: { events: AgentEvent[]; failed: boolean }) {
  const started = events.length > 0

  return (
    <section className="panel timeline">
      <h2>Investigation</h2>
      {!started && <p className="muted">Waiting for the agent to start…</p>}

      <ol className="phases">
        {PHASES.map(({ key, label }) => {
          const state = phaseState(key, events, failed)
          // Every query the agent ran in this phase, shown as it happens --
          // the SQL is the visible proof it is really querying ClickHouse.
          const queries = events.filter((e) => e.phase === key && e.type === 'query')
          const startEvent = events.find((e) => e.phase === key && e.type === 'phase_start')

          return (
            <li key={key} className={`phase phase--${state}`}>
              <div className="phase__head">
                <span className="phase__dot" aria-hidden />
                <span className="phase__label">{label}</span>
                {startEvent && <time className="phase__time">{clockTime(startEvent.at)}</time>}
              </div>

              {queries.length > 0 && (
                <ul className="queries">
                  {queries.map((q, i) => (
                    <li key={i} className="query">
                      <div className="query__meta">
                        <span className="query__badge">ClickHouse</span>
                        <time>{clockTime(q.at)}</time>
                      </div>
                      <pre className="query__sql">{(q.sql ?? q.tool ?? '').trim()}</pre>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
