---
name: time-locked-search
description: |
  Search the web as it was on a past date, with a date window the model cannot change. Use this skill for backtests, forecasting replays, evaluating a prediction against what was knowable at the time, or any question phrased as "what was known on date X", "as of", "before the announcement", "point-in-time", "no look-ahead". Wraps Tavily search with start_date/end_date and filter_by_published_date always on, checks every result's date again in code, flags undated pages instead of trusting them, and logs Tavily's request_id plus a SHA-256 of each response.
allowed-tools: Bash(python *)
---

# time-locked search

> Let the model program its filters, inside a time lock it cannot move.

The model chooses the query, topic, domains and result count. Code owns the dates. A search for "what was knowable
on 29 May 2026" can never see a page published on 30 May, even if the model asks for it or Tavily's date filter
misses one.

## When to use

- Backtests and replays: rebuild a forecast, nowcast or trading signal from evidence available on a past cutoff.
- Forecast evaluation: was this prediction made with information that existed at the time?
- Questions of the form "what was knowable on date X", "as of", "before the decision was announced".

Not for ordinary current-events search: use tavily-search there.

## The rules

1. **Fixed date window the model can't change.** The cutoff (and optional window start) is set by the calling code
   or the user, never by the model. Every call sends `start_date`, `end_date` and `filter_by_published_date=true`.
   An `end_date` after the cutoff, `filter_by_published_date` other than true, `time_range`, `days` or
   `auto_parameters` raises `TimeLockError` before any call (`auto_parameters` can pick its own `time_range`).
2. **Undated results are flagged, not trusted.** A result with no published date and no date in its address is
   labelled `date_flag`, never `safe`. Use it only after its date is established
   another way (for example a page date read from the page itself, or an archive capture before the cutoff).
3. **Every date is checked again in code.** `check_result` reads Tavily's `published_date`, any `/YYYY/MM/DD/` date
   in the address, and the page's own date when it was extracted. Any date after the cutoff makes the result a
   `leak`, even when Tavily's filter returned it; drop it.
4. **Quotes are verified on the page.** A snippet is a pointer, not evidence. Read the page (Tavily Extract), take
   the exact line that holds the fact, and check the number is in that line before using it. Never let the model
   write or paraphrase a quote.
5. **Keep the receipt.** Each call returns and logs Tavily's `request_id` and the response's SHA-256, so anyone can
   check later that the evidence came from that exact response. `usage.credits` can read 0 for calls below Tavily's
   reporting threshold; count spend from your ledger or `/usage`.

## How to call it

```python
from timelock import TavilyHTTP, timelocked_search      # standard library only; key from TAVILY_API_KEY

results = timelocked_search(TavilyHTTP(), "RBI repo rate decision October 2026", cutoff="2026-10-06",
                            topic="news", max_results=5,                   # the model may set these
                            include_domains=["rbi.org.in", "livemint.com"])
results.safe()      # dated on or before the cutoff: usable after the page check (rule 4)
[r for r in results if r["status"] == "date_flag"]     # undated: not trusted
[r for r in results if r["status"] == "leak"]          # dated after the cutoff: drop
results.counts, results.request_id, results.response_sha256
```

Each result keeps Tavily's fields plus `published_date` (ISO), `page_date`, `status`, `request_id` and
`response_sha256`. The window defaults to the 30 days ending on the cutoff; `start_date`/`end_date` may narrow it,
never extend it. `include_raw_content=True` lets the page's own published/updated date count (`page_date`);
`page_dates={url: "2026-10-05"}` adds a date read another way. Any client with `.search(query, **kwargs) -> dict`
works (tavily-python's `TavilyClient`, or `timelock.Replay` for a saved response, 0 credits).

Code: `timelock/` in the Shadow CPI repository (example: `examples/timelock_rbi.py`, "Use it in 10 lines" in the
README). Evidence that the lock matters: the "Time-locked search leakage" table at the top of the app's Tavily field
report.
