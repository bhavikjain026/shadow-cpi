#!/usr/bin/env python3
"""Start mcp/server.py over stdio with a real MCP client and call timelocked_search once on the saved RBI response.
No Tavily key is passed to the server and TIMELOCK_REPLAY is set, so no Tavily call is possible (0 credits).

    .venv/bin/python mcp/client_check.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "timelock" / "rbi_2026-10-06_locked.json"
ARGS = {"query": "RBI monetary policy repo rate decision October 2026", "cutoff": "2026-10-06", "topic": "news"}


async def main():
    server = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp" / "server.py")],
                                   env={"TIMELOCK_REPLAY": str(FIXTURE)})       # no TAVILY_API_KEY
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            print("server:", init.serverInfo.name, init.serverInfo.version)
            print("tools:", [t.name for t in tools.tools])
            result = await session.call_tool("timelocked_search", ARGS)
            print("isError:", result.isError)
            out = result.structuredContent or json.loads(result.content[0].text)
            out = out.get("result", out)
            print(json.dumps({k: out[k] for k in ("cutoff", "window", "counts", "request_id", "response_sha256")},
                             indent=1))
            for r in out["results"]:
                print(r["status"], r["published_date"], r["url"])


if __name__ == "__main__":
    asyncio.run(main())
