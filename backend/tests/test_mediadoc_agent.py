"""Self-check: MCP wiring in mediadoc_agent works end to end (no Gemini call,
no API key needed) -- connects over stdio, lists tools, runs a real query."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from backend.app.agents.mediadoc_agent import _mcp_server_params


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
    asyncio.run(main())
