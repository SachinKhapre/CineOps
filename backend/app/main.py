"""MediaDoc API (§10, §52): start an investigation, watch it progress over
SSE, read the result."""
import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app import config
from backend.app.agents.mediadoc_agent import investigate
from backend.app.investigations.session import STORE, Investigation

app = FastAPI(title="MediaDoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


async def _run(inv: Investigation):
    try:
        result = await investigate(inv.question, on_event=inv.add_event)
        inv.finish(result, "failed" if "error" in result else "complete")
    except Exception as exc:  # an investigation dying must not kill the server
        inv.add_event({"type": "error", "error": str(exc)})
        inv.finish({"error": str(exc)}, "failed")


@app.post("/api/investigations", status_code=201)
async def create_investigation(request: InvestigationRequest):
    inv = Investigation(request.question)
    STORE[inv.id] = inv
    # Run in the background so the client gets an id immediately and can
    # subscribe to /events; investigations take ~80s.
    asyncio.create_task(_run(inv))
    return inv.summary()


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    inv = STORE.get(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="investigation not found")
    return inv.summary()


@app.get("/api/investigations/{investigation_id}/events")
async def stream_events(investigation_id: str):
    inv = STORE.get(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="investigation not found")

    async def event_source():
        async for event in inv.stream():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        # Without this, nginx-style proxies buffer SSE and the timeline
        # arrives all at once at the end.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
