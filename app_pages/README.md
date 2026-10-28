# Shadow CPI app — pages and the file formats they read

Run: `pip install -r requirements-app.txt` then `streamlit run app.py`.

The app only **reads files**. It makes no API calls and needs no keys.

## Data

The app reads the real results files in this repository; there is no sample data. Every number on screen and its
file are listed in `docs/app_numbers.md`. Files that the pipeline keeps out of git (`logs/`, `cache/`) reach the app
as committed snapshots in `results/app/`, rebuilt with `python tools/build_app_data.py` (0 credits).

The only API calls are the capped "Run live" button on Home (`shadow_cpi/live_run.py`): off unless `RUN_LIVE_ENABLED`
is set; then 3 per visitor session, 8 per day for the app, none below a 100-credit ledger floor, and none unless
Tavily's GET /usage (checked before every run) reports at least 150 credits left. Keys from the environment only.

"Try it: search the past" (`app_pages/try_it.py`, `shadow_cpi/try_it.py`) runs a visitor's question twice (plain
search; `timelocked_search`) on the Tavily key whenever it is set, under its own caps in `config/budget.json`
(`plans["try-it"]`, caps `try-it` and `try-it-day`) and the account floors of `plans.app_live`. With no key it shows a
saved example (one Leak demo case).

| Page | File(s) |
| --- | --- |
| Home | `sealed/2026-10.json` (or `results/nowcast_2026-10.json`), `results/score_lock.json`, `results/scoreboard.md`, `results/app/audit_summary.json`, `results/app/saved_run.json` |
| Evidence | `manifests/<month>.json`, `data/spine.csv` |
| Replay | `results/score_lock.json`, `results/scoreboard.md`, `results/replay.csv`, `results/baselines.csv`, `results/tavily_attribution.csv` |
| Try it: search the past | live searches; saved example from `results/leak_demo.json`, `results/date_field_test.json` |
| Tavily trace (March) | `results/app/tavily_trace_2026-03.json` |
| Tavily Flight Recorder | `results/app/flight_recorder.jsonl`, `results/tavily_report_card.md` |
| Archive | `sealed/<month>.json` + `.sha256`, `data/official_releases.csv` |
| Reporter brief | `results/reporter_brief_<month>.md` |

A missing file never crashes a page; the page says which file it is waiting for.

## Formats read exactly as they exist today

- `results/baselines.csv` — `month,actual_yoy,b1_pred,b1_source,b1_miss,b2_pred,b2_miss,poll_pred,poll_miss` (blank poll = no dated article).
- `data/cpi_tidy.csv` — `month,level,code,name,weight,index,published_yoy,imputed`.
- `logs/flight_recorder.jsonl` — one JSON object per line, as written by `shadow_cpi/recorder.py`:
  `id, time, service ("tavily"|"nebius"), endpoint, params{query|urls|url|topic|start_date|end_date|…|model}, cached, latency_ms,
  parent (id of the call that led to this one, or null), tag, cache_key`, plus optional `n_results, n_failed, credits`.
  Credits are counted like `recorder.credits_used` (Tavily, not cached).
  **Assumed `tag` convention** (the recorder leaves it free): `"<job> <detail>"`, where job is `item:<name>`, `event:<name>`,
  `chase:<what>` (evidence-chase follow-ups, children of the verified event's call) or `circulars:<site>`.
  The app groups the "one item, end to end" trace by the first word, and draws trees from `parent`.
- `sealed/<month>.json` + `sealed/<month>.sha256` — canonical JSON from `shadow_cpi/seal.py`; the SHA-256 is of the file text.

## Assumed formats (files that do not exist yet)

### `results/nowcast_latest.json` (Prompt 3 output for the month being nowcast; also the sealed payload)
```json
{"target_month": "2026-10", "headline_yoy": 5.31, "range_low": 4.86, "range_high": 5.82, "range_level": 0.8,
 "replay_inside_range": {"n": 8, "of": 9},
 "coverage": {"observed": 0.31, "carried": 0.69},
 "contributors": [{"code": "01", "name": "Food and beverages", "pp": 2.71}],
 "tavily_attribution": {"pred_without_tavily": 5.13, "pred_with_tavily": 5.31, "coverage_without": 0.22, "coverage_with": 0.31},
 "evidence_cutoff_utc": "...", "manifest": "manifests/2026-10.json", "code_commit": "...",
 "model_ids": {"small": "...", "mid": "...", "large": "..."}, "weights_file_sha256": "..."}
```
Contributors are sorted largest first; the app shows the first 3. "Inside range N of 9" is taken from `results/replay.csv`
when it exists, else from `replay_inside_range`.

### `sealed/<month>.json` (Prompt 5)
The nowcast object above + `target_month`, `sealed_at_utc` (added by `seal.seal`) and `git_tag` (e.g. `seal-2026-10`).

### `manifests/<month>.json` (Prompt 2C)
```json
{"month": "2026-10", "created_utc": "...", "code_commit": "...", "model_ids": {...},
 "queries": [{"call_id": "...", "endpoint": "search", "query": "...", "language": "en|hi", "params": {...},
              "retrieved_at": "...", "n_results": 8}],
 "counts": {"pages_seen": 41, "pages_kept": 17, "quotes_extracted": 38, "quotes_verified": 24,
            "events_extracted": 6, "events_verified": 4},
 "dropped": [{"reason": "outside the month (date check)", "count": 9}],
 "quotes": [{"item": "onion", "price": 42.0, "unit": "Rs/kg", "place": "Delhi", "date": "2026-10-14",
             "tier": "strict|exploratory", "source": "spine|tavily", "line": "<exact page line>", "url": "...", "verified": true}],
 "events": [{"item": "milk", "seller": "...", "place": "...", "pct_change": 3.6, "old_price": 56, "new_price": 58,
             "unit": "Rs/litre", "announced_date": "...", "effective_date": "...", "days_in_month_share": 0.871,
             "line": "<exact page line>", "url": "...", "verified": true, "confirmed_by_2_sources": true}],
 "failed_sources": [{"url": "...", "via": "tavily extract", "reason": "..."}]}
```
Only `verified: true` quotes and events are shown.

### `data/spine.csv` (Prompt 2A)
`month,item,centre,avg_price,unit,n_days,tier`

### `results/replay.csv` (Prompt 3)
`month,actual_yoy,a_trend_pred,b_spine_pred,c_tavily_pred,c_range_low,c_range_high,c_inside_range,b_coverage_observed,c_coverage_observed,tier,note`
(`c_inside_range` is `True`/`False`; `note` = plain-English explanation of a miss, may be blank).
The app joins B1 and poll from `results/baselines.csv` by month and computes the scoreboard (mean absolute miss;
direction right = up/down vs the previous month's official rate, which is B1's prediction).

### `results/tavily_attribution.csv` (Prompt T4)
`month,pred_without_tavily,pred_with_tavily,coverage_without,coverage_with,actual_yoy,miss_without,miss_with,tavily_calls,credits`

### `results/tavily_report_card.md` (Prompt T5)
Free Markdown, shown as is.

### `results/skeptic_<month>.json` ("Try to prove this wrong", cached result)
```json
{"month": "2026-10", "ran_at_utc": "...",
 "checked": [{"contributor": "...", "counter_query": "...", "contrary_verified_quotes": 1}],
 "widened": false, "reason": "...",
 "receipt": {"tavily_calls": 3, "credits": 3, "seconds": 12.4, "nemotron_calls": 4}}
```

### `results/run_now_cached.json` ("Run now", last cached event scan)
```json
{"ran_at_utc": "...", "window_start": "2026-10-12", "window_end": "2026-10-18", "daily_cap": 2, "credit_cap": 20,
 "events": [{"item": "milk", "place": "...", "pct_change": 3.6, "effective_date": "...", "line": "...", "url": "...", "verified": true}],
 "receipt": {"tavily_calls": 9, "credits": 14, "seconds": 38.2, "nemotron_calls": 11}}
```
Both buttons currently show only the cached result, with a note that live runs come later.

### `results/reporter_brief_<month>.md`
Markdown with the sections What moved / What we observed / What's uncertain. The page warns if the text does not
mention "coverage" and "range".

### `data/official_releases.csv` (Prompt 5.4)
`month,official_yoy,release_date,source_url` — the Archive shows the miss and inside-range once a month appears here.

