"""Self-check: MCP wiring in mediadoc_agent works end to end (no Gemini call,
no API key needed) -- connects over stdio, lists tools, runs a real query."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from backend.app.agents.mediadoc_agent import _mcp_server_params, compute_confidence, parse_json_response


def test_offline():
    assert parse_json_response('{"a": 1}') == {"a": 1}
    assert parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_response("not json")["error"]

    assert compute_confidence([]) == {"score": 0, "band": "Low"}
    assert compute_confidence([{"supported": True, "strength": "strong"}, {"supported": True, "strength": "strong"}]) == {"score": 100, "band": "Very High"}
    assert compute_confidence([{"supported": True, "strength": "weak"}]) == {"score": 33, "band": "Moderate"}
    # ruling out an alternative hypothesis (supported=false) must not drag down confidence in the one that IS supported
    assert compute_confidence([{"supported": True, "strength": "strong"}, {"supported": False, "strength": "contradictory"}]) == {"score": 100, "band": "Very High"}
    # nothing supported at all -> no basis for confidence
    assert compute_confidence([{"supported": False, "strength": "contradictory"}]) == {"score": 0, "band": "Low"}
    print("offline checks ok")


async def main():
    params = _mcp_server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"list_databases", "list_tables", "run_query"} <= names, names

            result = await session.call_tool("run_query", {"query": "SELECT count() AS n FROM mediadoc.viewing_events"})
            assert "n" in result.content[0].text

    print("ok")


if __name__ == "__main__":
    test_offline()
    asyncio.run(main())
