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
cp .env.example .env
docker compose up -d clickhouse
```
