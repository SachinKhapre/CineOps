# MediaDoc

Autonomous entertainment intelligence agent. Investigates ambiguous operational
problems ("something went wrong yesterday") over ClickHouse-stored viewing
events via the `mcp-clickhouse` MCP server, and returns an evidence-backed
root cause and recommendation.

See `MediaDoc — End-to-End Project Blueprint.md` for the full spec.

## Layout

- `backend/` — FastAPI app, Gemini agent, investigation engine
- `frontend/` — investigation console UI
- `data/generator/` — synthetic event + incident generator
- `clickhouse/` — schema, seeds, reference queries
- `mcp/clickhouse/` — MCP server config
- `docs/` — architecture, methodology, demo script
- `scripts/` — setup / seed / demo-reset helpers

## Setup

```
cp .env.example .env          # then add your GOOGLE_API_KEY
pip install -r backend/requirements.txt -r data/generator/requirements.txt
docker compose up -d clickhouse
python data/generator/generate.py --scale medium
```

`--scale small` seeds faster but the injected incident gets lost in sampling
noise; `medium` (~1.3M events) is the smallest scale where detection is
reliable.

## Run

```
uvicorn backend.app.main:app --reload   # API on :8000
cd frontend && npm install && npm run dev   # console on :5173
```

The console is the intended way in — open http://localhost:5173, ask a
question, and watch the investigation stream. Vite proxies `/api` to the
backend, so there's no CORS setup or API base URL to configure.

The API on its own:

- `POST /api/investigations` `{"question": "..."}` → starts one, returns an id
- `GET  /api/investigations/{id}/events` → SSE progress (phases + each SQL query)
- `GET  /api/investigations/{id}` → status and final result
- `GET  /api/health`

The agent can also be run directly:
`python backend/app/agents/mediadoc_agent.py "what broke yesterday?"`

## Tests

```
python backend/tests/test_api.py             # API layer, agent stubbed
python backend/tests/test_mediadoc_agent.py  # MCP wiring + scoring logic
python data/generator/test_generate.py       # incident injection
python backend/tests/eval_agent.py --runs 3  # scores the agent vs ground truth
```

The first three are free. `eval_agent.py` calls Gemini for real (~11 model
calls per run).
