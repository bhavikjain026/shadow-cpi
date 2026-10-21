# Numbers the app shows, and where each comes from

Every number on screen is read from a file in this repository at page load; the app computes only formatting, the
countdown (release time minus now) and counts of rows. Values below are as of the commit that adds this file;
rebuild `results/app/` with `python tools/build_app_data.py`.

| Page | Number | Value now | Source file → field |
|---|---|---|---|
| Home | October call: headline YoY, 80% range, P(headline ≥ 6.0%), coverage, top 3 contributors, SHA-256, sealed time | not shown yet: “sealing on 29 Oct” | `sealed/2026-10.json` (else `results/nowcast_2026-10.json`, labelled “not sealed yet”): `headline_yoy`, `range_low`, `range_high`, `p_headline_ge_6`, `coverage`, `contributors`, `sealed_at_utc`; `sealed/2026-10.sha256` |
| Home | Headline result: Shadow CPI average miss; number of poll months; Shadow CPI vs poll on those months | 0.194 percentage points; 6; 0.150 vs 0.148 (“about a tie”: within 0.005) | `results/score_lock.json` `mae.c`, `mae_poll_months.c`, `mae_poll_months.poll`; poll months counted in `results/baselines.csv` (`poll_pred` filled) |
| Home, Replay | Pass/fail rule result | passed | `results/score_lock.json` `go` |
| Home | Seal date “29 Oct” | 2026-10-29 | `app_pages/common.py` `SEAL_DATE`, from `seal_checklist.md` |
| Home | Threshold 6.0% (RBI projection, Oct–Dec 2026) | 6.0 | `shadow_cpi/live_range.py` `THRESHOLD`; checked in `audit/dates_check.md` (c) |
| Home | Countdown to the official October CPI | Thu 12 Nov 2026, 4:00 PM IST, minus the current time | `app_pages/common.py` `RELEASES`, `RELEASE_HOUR_IST`; checked in `audit/dates_check.md` (a) |
| Home, Replay | (a) Trend only: mean miss after / before fixes, direction right | 0.212 / 0.212 pp, 8 of 9 | `results/score_lock.json`: `mae`, `history[-1].mae`, `direction_hits` |
| Home, Replay | (b) Spine only: mean miss after / before fixes, direction right | 0.225 / 0.225 pp, 9 of 9 | `results/score_lock.json`: `mae`, `history[-1].mae`, `direction_hits` |
| Home, Replay | (c) Spine + Tavily: mean miss after / before fixes, direction right | 0.194 / 0.185 pp, 7 of 9 | `results/score_lock.json`: `mae`, `history[-1].mae`, `direction_hits` |
| Home, Replay | (c-strict): mean miss after / before fixes, direction right | 0.204 / 0.204 pp, 8 of 9 | `results/score_lock.json`: `mae`, `history[-1].mae`, `direction_hits` |
| Home, Replay | B1 last month: mean miss after / before fixes, direction right | 0.468 / 0.468 pp, 0 of 9 | `results/score_lock.json`: `mae`, `history[-1].mae`, `direction_hits` |
| Home, Replay | Economists' poll: mean miss on its 6 months (after / before) | 0.148 / 0.148 pp | `results/score_lock.json` `mae_poll_months.poll` |
| Home, Replay | Poll direction right | 6 of 6 | `results/scoreboard.md` (the lock file does not store it) |
| Home, Replay | (c) on the poll's 6 months | 0.150 pp | `results/score_lock.json` `mae_poll_months.c` |
| Home | Actual inside the 80% range | GO; 5 of 9 | `results/score_lock.json` `go`, `inside_range` |
| Home | Audit: events checked; correct / partly / wrong / unclear | 12; 5 / 3 / 3 / 1 | `results/app/audit_summary.json` ← `audit/event_audit.csv` (cross-checked with `audit/event_audit.md`) |
| Home | Audit: confirmed by a second source | 9 | `results/app/audit_summary.json` ← `audit/event_audit.md` |
| Home | Fixes made; events before → after | 4; 12 → 9 | `results/app/audit_summary.json` ← `docs/after_scoring_changes.md` §4, `audit/event_audit.csv`, `manifests/2026-0*.json` |
| Home | Recall: found directly; including official series | 9 of 29; 14 of 29 | `results/app/audit_summary.json` ← `audit/missed_events.md` (table rows counted, checked against its stated totals) |
| Home | Saved run: evidence window, replayed-on date, searches, credits when first run, events | 2026-08-22 to 2026-09-30; 2026-10-21; 18 searches; 39 credits; 1 event | `results/app/saved_run.json` ← `manifests/2026-09.json` (`created_utc`, `queries`, `events`, `detail.event_search_window`), `results/replay_layers.csv` (credits) |
| Home | Live-run limits in messages | off until RUN_LIVE_ENABLED is set (“Live runs open on 1 Dec”); 3 per visit, 8 per day, ledger floor 100 credits, Tavily /usage floor 150 credits | `RUN_LIVE_ENABLED` (Space setting); `config/budget.json` `plans.app_live`; Tavily GET /usage `account.plan_limit − account.plan_usage` (checked before each run, not stored); per-scan caps `caps.run-now-scan` (8), `caps.run-now` (120) |
| Home | Live-run receipt (only after a live run) | computed during the run | `shadow_cpi/live_run.py` (flight recorder lines tagged `live:`, Budgeted credits) |
| Evidence | Quotes, events, counts, dropped reasons, failed sources, searches, code commit, model IDs | per month | `manifests/<month>.json` |
| Evidence | Spine prices | per month | `data/spine.csv` |
| Evidence | “Price quotes listed above: N” (official-series rows, news quotes) | March 50 (38, 12) | counted from the same verified quote rows the table shows (`manifests/<month>.json` `quotes`) |
| Evidence | Latest event search: pages seen, kept, events verified of extracted | per month | `manifests/<month>.json` `counts` (that run's event layer only) |
| Flight Recorder | Default “one verified event, end to end” chain | September 2026 J&K electricity | `results/app/event_chains.json` ← full `logs/flight_recorder.jsonl` |
| Replay | Per-month actual, (a), (b), (c), range, inside, coverage; chart | 9 months | `results/replay.csv` |
| Replay | B1 and poll per month | 9 months | `results/baselines.csv` |
| Replay | Inside the range (count) | 5 of 9 | `results/replay.csv` `c_inside_range` |
| Replay | With / without Tavily, per month | 9 months | `results/tavily_attribution.csv` |
| Tavily trace | Calls, credits, failures listed | 117, 110, 14 | `results/app/tavily_trace_2026-03.json` ← flight recorder, cache, `results/credit_ledger.jsonl` |
| Tavily trace | Funnel: Addresses found by Tavily search | 429 | `results/app/tavily_trace_2026-03.json` ← flight recorder + cache |
| Tavily trace | Funnel: Dated inside the search window | 323 | `results/app/tavily_trace_2026-03.json` ← page address / published date |
| Tavily trace | Funnel: Pages read by Tavily Extract | 226 | `results/app/tavily_trace_2026-03.json` ← flight recorder |
| Tavily trace | Funnel: Pages checked by the gatekeeper model | 62 | `results/app/tavily_trace_2026-03.json` ← flight recorder (Nemotron) |
| Tavily trace | Funnel: Pages read for prices or events | 61 | `results/app/tavily_trace_2026-03.json` ← flight recorder (Nemotron) |
| Tavily trace | Funnel: Price quotes extracted / verified word-for-word | 93 / 91 | `results/app/tavily_trace_2026-03.json` ← manifests/2026-03.json at f00bd45 (Prompt 2 quote run) |
| Tavily trace | Funnel: Price events extracted / verified | 47 / 0 | `results/app/tavily_trace_2026-03.json` ← manifests/2026-03.json |
| Tavily trace | Funnel: Numbers used in the (c) prediction | 11 | `results/app/tavily_trace_2026-03.json` ← results/replay_predictions.json |
| Tavily trace | Item names next to the codes in “Numbers used” (e.g. Onion (01.1.7.4.1.01)) | 11 items | `results/app/tavily_trace_2026-03.json` ← names from the weights file `data/official/mospi_cpi2024_weights_Annex_5.3.xlsx` (Annex 5.3d) |
| Tavily trace | Each call: endpoint, settings changed, credits, seconds, produced | 117 rows | `results/app/tavily_trace_2026-03.json` `calls` |
| Flight Recorder | Tavily calls; credits used; from cache; Nemotron calls | 6652; 694; 5865; 10006 | `results/app/flight_recorder.jsonl` (snapshot of `logs/flight_recorder.jsonl`) |
| Flight Recorder | Report card | as written | `results/tavily_report_card.md` |
| Archive | Sealed number, range, SHA-256, official figure, miss | nothing sealed yet | `sealed/<month>.json` + `.sha256`, `data/official_releases.csv` |
| Reporter brief | September 2026 example (labelled “Example from replay month — not a forecast”): Shadow CPI, range, coverage, contributions, item changes, observed changes, event, skeptic count, inside-range count, official figure and miss | 5.80%; 5.78–6.14%; 21% measured; … | `results/reporter_brief_2026-09.md`, written by `tools/build_app_data.py` from `results/replay.csv`, `results/replay_predictions.json`, `results/replay_layers.csv`, `manifests/2026-09.json`, `results/skeptic_replay.json`, `results/score_lock.json`; names from `data/cpi_tidy.csv` and the weights file (Annex 5.3d) |

**Nothing shows sample data.** `data/sample/` was removed; `tests/test_app_pages.py` checks that no page shows
the word SAMPLE and that the folder is gone.
