"""Connects to mcp-clickhouse over stdio and runs a real query through it.
Proves the MCP integration works end to end (not just that ClickHouse is up).
"""
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CONFIG = json.load(open(os.path.join(os.path.dirname(__file__), "..", "mcp", "clickhouse", "config.json")))
SERVER = CONFIG["mcpServers"]["clickhouse"]


async def main():
    venv_python = os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts", "python.exe")
    command = venv_python if os.path.exists(venv_python) else SERVER["command"]
    args = ["-c", "from mcp_clickhouse.main import main; main()"] if command == venv_python else []
    params = StdioServerParameters(command=command, args=args, env={**os.environ, **SERVER["env"]})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            result = await session.call_tool(
                "run_query",
                {"query": "SELECT count() AS n FROM mediadoc.viewing_events"},
            )
            print("query result:", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
