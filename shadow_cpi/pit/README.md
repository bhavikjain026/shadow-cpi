# shadow_cpi.pit: time-locked search

The pipeline's wrapper around the standalone [`timelock/`](../../timelock/) module (use that outside Shadow CPI):
it adds the Flight Recorder, a month-start window and the kept/flagged/leaks split.

Let the model program its filters, inside a time lock it cannot move.

`pit_search(query, cutoff)` always sends `start_date`/`end_date` and `filter_by_published_date=true` (plus
`include_usage`), refuses any parameter that would move the window (`start_date`, `end_date`,
`filter_by_published_date`, `time_range`, `days`, `auto_parameters`), keeps Tavily's `request_id` and the response's
SHA-256, and runs `check_result` on every result: safe results are kept, undated ones are flagged (not trusted), and
any result dated after the cutoff is dropped as a leak even if Tavily's filter let it through.

```python
from shadow_cpi.pit import pit_search, as_of

r = pit_search("petrol diesel price hike India May 2026", cutoff="2026-05-29",
               topic="news", max_results=3)            # window 2026-05-01 .. 2026-05-29, locked
print(r["counts"])                 # {'safe': 3, 'date_flag': 0, 'leak': 0}
for x in r["kept"]:                # only results dated on or before the cutoff
    print(x["published_date"], x["url"])
print(r["request_id"], r["response_sha256"][:12], r["credits"])
view = as_of("2026-09-15")         # Shadow CPI's own nowcast + evidence as known that day (0 credits)
```

`credits` is Tavily's `usage.credits` as returned: it can read 0 for calls below Tavily's reporting threshold, so
count spend from the ledger or `/usage`. Tests use saved responses only: `tests/test_pit.py`.
Agent instructions: `skills/time-locked-search/SKILL.md`.
