# timelock MCP server

One tool, `timelocked_search(query, cutoff, ...)`: a Tavily search that cannot see past the cutoff, for any MCP
client. It wraps [`timelock/`](../timelock/) (the date window is sent to Tavily with `filter_by_published_date`, then
every result is checked again in code). The agent picks the query, topic, domains and result count; the cutoff is
fixed by the task, and an `end_date` after it is refused.

What the agent gets back: `counts`, the `window`, Tavily's `request_id`, the response's `response_sha256`, and the
results. Results dated on or before the cutoff (`safe`) include title and snippet. Undated results (`date_flag`) and
results dated after the cutoff (`leak`) come back as domain, dates and status only: the agent knows they exist but
never reads their text or their URL (a news URL's slug often states the outcome).

## 1. Install

From the repository root (Python 3.10 or later):

```bash
python -m pip install -r mcp/requirements.txt
```

You need a Tavily API key (each call costs 1 credit at `search_depth="basic"`). To try it with no key and no
credits, set `TIMELOCK_REPLAY` to a saved response instead (it answers only the question it was recorded for:
"RBI monetary policy repo rate decision October 2026", cutoff 2026-10-06, `topic="news"`).

Use the absolute path to `mcp/server.py` below; `/path/to/shadow-cpi` stands for your clone.

## 2a. Claude Code

```bash
claude mcp add timelock -e TAVILY_API_KEY=your-key -- python /path/to/shadow-cpi/mcp/server.py
```

Check it with `claude mcp list`, then ask, for example: *"Using timelocked_search with cutoff 2026-10-06, what did
analysts expect from the RBI's October 2026 policy decision?"* Without a key:

```bash
claude mcp add timelock -e TIMELOCK_REPLAY=/path/to/shadow-cpi/tests/fixtures/timelock/rbi_2026-10-06_locked.json -- python /path/to/shadow-cpi/mcp/server.py
```

## 2b. Claude Desktop

Open Settings → Developer → Edit Config (the file is `~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows) and add:

```json
{
  "mcpServers": {
    "timelock": {
      "command": "python",
      "args": ["/path/to/shadow-cpi/mcp/server.py"],
      "env": {"TAVILY_API_KEY": "your-key"}
    }
  }
}
```

Use the full path to the Python that has `mcp` installed if `python` is not on Claude Desktop's PATH (for example
the output of `which python`). Restart Claude Desktop; `timelocked_search` appears under the tools icon.

## Tests

`tests/test_timelock_mcp.py` runs the tool on the saved RBI response (no key, no network, no `mcp` package needed)
and checks the server registers it under FastMCP.
