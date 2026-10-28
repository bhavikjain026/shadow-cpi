# timelock MCP server

Two tools for any MCP client. `timelocked_search(query, cutoff, ...)`: a Tavily search that cannot see past the
cutoff. `extract_as_of(url, cutoff, published_date=None)`: the page's text as it was on the cutoff (the live Extract if
nothing suggests it changed since, else the latest Wayback capture on or before the cutoff), or no text and the reason
"no as-of copy". With no capture on or before the cutoff to confirm an unchanged page, the live text comes back
labelled "unverified: no archive copy before the cutoff" (`strict=true` refuses it); an Extract answer for another
address is refused as "url mismatch". It needs a live key (1 credit per call) and downloads from the Wayback Machine directly. It wraps [`timelock/`](../timelock/) (the date window is sent to Tavily with `filter_by_published_date`, then
every result is checked again in code). For the search, the agent picks the query, topic, domains and result count; the cutoff is
fixed by the task, and an `end_date` after it is refused.

What the agent gets back: `counts`, the `window`, Tavily's `request_id`, the response's `response_sha256`, and the
results. Results dated on or before the cutoff (`safe`) include title and snippet. Undated results (`date_flag`) and
results dated after the cutoff (`leak`) come back as domain, dates and status only: the agent knows they exist but
never reads their text or their URL (a news URL's slug often states the outcome).

## 1. Install and check it (tested)

These exact steps were run on 27 Oct 2026 (macOS, Python 3.14.7, `mcp` 1.30.0), from the repository root. The venv
keeps `mcp` out of the project's own requirements (`.venv/` is git-ignored):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r mcp/requirements.txt
.venv/bin/python mcp/client_check.py
```

`mcp/client_check.py` is a real MCP client: it starts `mcp/server.py` over stdio with `TIMELOCK_REPLAY` set to the
saved RBI response and no Tavily key (so no Tavily call is possible), initialises a session, lists the tools and
calls `timelocked_search` once. Output of that run:

```text
server: timelock 1.30.0
tools: ['timelocked_search']
isError: False
{
 "cutoff": "2026-10-06",
 "window": [
  "2026-09-07",
  "2026-10-06"
 ],
 "counts": {
  "safe": 5,
  "date_flag": 0,
  "leak": 0
 },
 "request_id": "5e7387cb-67c8-455d-931d-fab9b7523f49",
 "response_sha256": "f147da6d345b41aff5ab9c49a1802910df93c66478a7a5370ed045a3be78bde2"
}
safe 2026-10-05 https://www.newindianexpress.com/business/2026/Oct/05/october-monetary-policy-meeting-why-a-25-basis-point-rate-hike-is-likely-this-time
safe 2026-10-06 https://www.business-standard.com/finance/news/rbi-mpc-october-2026-meeting-when-and-where-to-watch-rate-decision-live-126100600090_1.html
safe 2026-09-18 https://www.thehindu.com/business/Economy/rbi-may-deliver-two-rate-hikes-by-cy-2026analysts/article71481500.ece
safe 2026-09-16 https://www.rediff.com/business/report/rbi-monetary-policy-rate-hikes-expected-in-october-and-december-amid-inflation-surge/20260916.htm
safe 2026-09-23 https://timesofindia.indiatimes.com/business/india-business/your-loan-emi-has-a-washington-problem-how-the-fed-quietly-influences-rbi-rate-decisions/articleshow/134432773.cms
```

(The server also logs `Processing request of type ...` lines to stderr.) The request ID and hash are the saved
Tavily response's own.

You need a Tavily API key (each call costs 1 credit at `search_depth="basic"`). To try it with no key and no
credits, set `TIMELOCK_REPLAY` to a saved response instead (it answers only the question it was recorded for:
"RBI monetary policy repo rate decision October 2026", cutoff 2026-10-06, `topic="news"`).

The client setups below were not run as part of that check. Use absolute paths; `/path/to/shadow-cpi` stands for
your clone, and `/path/to/shadow-cpi/.venv/bin/python` is the venv's Python, which has `mcp` installed.

## 2a. Claude Code

```bash
claude mcp add timelock -e TAVILY_API_KEY=your-key -- /path/to/shadow-cpi/.venv/bin/python /path/to/shadow-cpi/mcp/server.py
```

Check it with `claude mcp list`, then ask, for example: *"Using timelocked_search with cutoff 2026-10-06, what did
analysts expect from the RBI's October 2026 policy decision?"* Without a key:

```bash
claude mcp add timelock -e TIMELOCK_REPLAY=/path/to/shadow-cpi/tests/fixtures/timelock/rbi_2026-10-06_locked.json -- /path/to/shadow-cpi/.venv/bin/python /path/to/shadow-cpi/mcp/server.py
```

## 2b. Claude Desktop

Open Settings → Developer → Edit Config (the file is `~/Library/Application Support/Claude/claude_desktop_config.json`
on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows) and add:

```json
{
  "mcpServers": {
    "timelock": {
      "command": "/path/to/shadow-cpi/.venv/bin/python",
      "args": ["/path/to/shadow-cpi/mcp/server.py"],
      "env": {"TAVILY_API_KEY": "your-key"}
    }
  }
}
```

Claude Desktop does not use your shell's PATH, so keep the full path to the venv's Python. Restart Claude Desktop;
`timelocked_search` appears under the tools icon.

## Tests

`tests/test_timelock_mcp.py` runs the tool on the saved RBI response (no key, no network) and checks the server
registers it under FastMCP: with the real package when it is installed (`.venv/bin/python -m pytest
tests/test_timelock_mcp.py`, after `.venv/bin/python -m pip install pytest`), with a stand-in otherwise.
