"""Self-check for the API layer. Stubs the agent, so this costs nothing to
run -- it exercises routing, session state and SSE, not investigation quality
(that's eval_agent.py, which does spend credits)."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.investigations.session import STORE

FAKE_RESULT = {"question": "q", "detection": {"anomaly_day": "2026-09-08"}, "stats": {"queries": 2}}


async def fake_investigate(question, on_event=None):
    on_event({"type": "phase_start", "phase": "detection"})
    await asyncio.sleep(0.01)
    on_event({"type": "query", "phase": "detection", "sql": "SELECT 1"})
    await asyncio.sleep(0.01)
    on_event({"type": "complete", "phase": "conclusion", "result": FAKE_RESULT})
    return FAKE_RESULT


async def failing_investigate(question, on_event=None):
    raise RuntimeError("gemini exploded")


def collect_events(client, inv_id):
    with client.stream("GET", f"/api/investigations/{inv_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return [
            json.loads(line[len("data: "):])
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]


def main_test():
    STORE.clear()
    main.investigate = fake_investigate
    client = TestClient(main.app)

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/investigations/nope").status_code == 404
    assert client.post("/api/investigations", json={"question": ""}).status_code == 422

    created = client.post("/api/investigations", json={"question": "what broke?"})
    assert created.status_code == 201, created.text
    inv_id = created.json()["id"]
    assert created.json()["status"] == "running"

    # The stream must replay from the beginning -- a subscriber that connects
    # late (or after completion) still needs the whole timeline, not a tail.
    events = collect_events(client, inv_id)
    assert [e["type"] for e in events] == ["phase_start", "query", "complete"], events
    assert events[1]["sql"] == "SELECT 1"

    # ... and connecting again after it's finished replays the same timeline.
    assert len(collect_events(client, inv_id)) == 3

    final = client.get(f"/api/investigations/{inv_id}").json()
    assert final["status"] == "complete", final
    assert final["result"] == FAKE_RESULT

    # A blown-up investigation marks the session failed instead of taking the
    # server down with it.
    main.investigate = failing_investigate
    failed_id = client.post("/api/investigations", json={"question": "boom"}).json()["id"]
    collect_events(client, failed_id)
    failed = client.get(f"/api/investigations/{failed_id}").json()
    assert failed["status"] == "failed", failed
    assert "gemini exploded" in failed["result"]["error"]
    assert client.get("/api/health").status_code == 200  # server still alive

    print("api checks ok")


if __name__ == "__main__":
    main_test()
