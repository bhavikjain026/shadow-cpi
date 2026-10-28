# Exa-style parameters on the Tavily time lock

`timelock/compat_exa.py` makes migration to Tavily easier for code that already passes Exa's `/search`
point-in-time parameters. It maps them onto `timelocked_search`, so the time lock's date window and filter are always sent.

```python
from timelock import TavilyHTTP
from timelock.compat_exa import exa_style_search

results = exa_style_search(TavilyHTTP(), query="RBI repo rate decision October 2026",
                           contents={"snapshotAsOf": "2026-10-07"},       # -> cutoff 2026-10-06
                           startPublishedDate="2026-09-07", numResults=5,
                           includeDomains=["rbi.org.in", "thehindu.com"])
print(results.cutoff, results.window, results.counts)
print(results.note)   # date-filtered by stated dates; not a historical snapshot of page content; ...
```

| Exa-style parameter | Time lock |
|---|---|
| `contents.snapshotAsOf` (or its deprecated alias `contents.crawledBeforeDate`) | `cutoff` = the last whole UTC day before it |
| `startPublishedDate` / `endPublishedDate` | `start_date` / `end_date` (end: the UTC day before it; also the cutoff if there is no snapshot) |
| `includeDomains` / `excludeDomains` | `include_domains` / `exclude_domains` |
| `numResults` | `max_results` |

Any other parameter (including other `contents` options) raises `UnsupportedParameterError` before any call. A
call with no cutoff raises `TimeLockError`. Names checked on 28 Oct 2026 against
https://exa.ai/docs/reference/search; re-check them there before relying on this.

The results are filtered by the dates they state, not a copy of each page as it was on the cutoff. For page
content as of the cutoff, use `extract_as_of` (`timelock/asof.py`).
