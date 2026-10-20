# Shadow CPI — build prompts (run in order; read CLAUDE.md first)

Track: **Best Apps and Agents** (not Personal AI). Bonus target: Best Use of Tavily.

Already done: Prompt 0 = `checks.py` (+ fixes: page-address dates, line-referenced quotes, India-focused searches, logged direct-download fallback).
The "fix quote extraction" follow-up is DONE: Nemotron now cites a numbered line and code takes that exact line (`verify.split_lines`, `nemotron._attach_lines`).

---------------------------------------------------------------------------------------------------

## Prompt 1 — official data and baselines (21 Oct)

First try to fetch the official files yourself (we are in India, so MoSPI may allow a direct download from this computer):
- 2024-series All-India **Combined** indices (groups, subgroups, and items if published), Jan 2025 – Sep 2026, from
  https://esankhyiki.mospi.gov.in/macroindicators?product=cpi or https://www.mospi.gov.in/cpi-sdmx-month-wise
  (fallback: the monthly MoSPI press-release PDFs; Tavily Extract can read them — tested OK).
- The 2024-series weights table (group, subgroup, item).
Save raw files to data/official/. If a download needs a browser, tell me exactly which file to download by hand.
Economists' polls: data/poll.csv (month, median_forecast, n_economists, source_url, published_at) — search with Tavily for the original dated article for each month Jan–Sep 2026; write "none" if not found. Never use an aggregator's number without a dated source.

Then build `shadow_cpi/official.py` + `build_official.py`:
1. Parse into data/cpi_tidy.csv: month, level (group/subgroup/item), code, name, weight, index.
2. Refuse to run if weights look like the 2012 series (food ≈ 45.86% instead of ≈ 36.75%).
3. Tell me whether item-level monthly indices + weights exist for: onion, tomato, potato, tur/arhar dal, edible oils, rice, atta, milk, eggs, gold, silver, LPG, petrol. If not, the finest level available.
4. Check: `cpi_math.aggregate` of subgroup LEVELS reproduces the published all-India index within 0.1 for every month. Full precision; never average percentage changes.
5. YoY Jan–Sep 2026 from the indices vs the press releases (0.01 rounding differences are fine).
6. 2025 = calibration only; Jan–Sep 2026 = test months, never used to set any parameter.
7. Baselines Jan–Sep 2026 with `cpi_math`: B1 = `b1_last_yoy`; B2 = `trend_change` per component (0.5 seasonal weight, fixed), aggregate predicted LEVELS. Report mean absolute miss (pp) for B1, B2 and the poll (dated months only). Save results/baselines.csv.
8. data/item_map.csv: tracked item → subgroup code, item weight, item index code (if published).
Add tests. No paid API calls except Tavily lookups for the poll articles (estimate credits first).

## Prompt 2 — evidence engine (21–22 Oct)

Build `shadow_cpi/evidence.py`. Nemotron extracts (line-referenced), code decides.
A) Spine — government daily retail prices (Consumer Affairs, 38 foods). Route: `Tavily.extract_or_download` (Tavily is blocked by the site, so the logged direct download from this computer is expected; if a form/date query is needed, find the report URL that takes a date range). Fallback mirror if needed: dataful.in dataset 19920 (Delhi, daily). Store centre-level monthly averages Jan 2025 – Oct 2026 in data/spine.csv. Item change = `verify.geometric_mean_change` over centres present in both months. Tag tier="strict".
A2) Pass-through factor per item/subgroup: fit on 2025 ONLY (official MoM vs spine MoM; a simple ratio is fine). Save to config/passthrough.json.
B) Tavily evidence layer, per month (date window = that month):
 1. items.yaml for what the spine lacks: gold, silver (OBSERVED daily from a published rate page found + extracted with Tavily, e.g. IBJA — never left on trend), LPG, petrol, plus any missing foods. English + Hindi (Devanagari) query templates.
 2. Search topic="news", search_depth="basic", max_results=8, start/end = month, include_domains=INDIAN_NEWS or HINDI_NEWS with include_domains_mode="prefer", exclude_domains=["mospi.gov.in"]. Extract top 6 with query=… and chunks_per_source=5. `Nemotron.price_quotes` (mid model) → keep only verified quotes.
 3. Dates: `tavily.best_date` (page address first). Drop anything outside the month. Leak guard: drop any page stating an official CPI/retail-inflation figure for the target month; count drops.
 4. Matching: compare a quote with the same item + same city/source last month; else with the spine price for that city. ≥3 independent matched quotes (dedupe syndicated copies with `verify.dedupe_quotes`), else None.
 5. EVENT LAYER (most important Tavily job): per month, search announced price changes across the basket — "milk price hike effective" (Amul, Mother Dairy, state co-ops), "LPG cylinder price revised", "electricity tariff order" (state regulators), "mobile tariff hike", "railway fare revision", "NPPA medicine price revision", "school fee hike", "GST rate change" — English + Hindi. `Nemotron.price_events` (mid model); keep verified; apply only if effective_date is inside the month, pro-rated by days.
 6. A cheap gatekeeper: the small model first answers yes/no "does this page state an Indian price or an announced price change?"; skip pages that say no.
C) manifests/<YYYY-MM>.json per month: queries, Tavily params, URLs, retrieval times, kept/dropped counts with reasons, code commit, model IDs.
Everything via Recorder (cache + flight recorder). Estimate credits for 10 months first and STOP if it exceeds the balance. Test on March 2026 first and show me spine values, verified quotes and events.

## Prompt T — Tavily at the centre (22 Oct)

1. All web data enters via Tavily; direct download only as the logged fallback (count fallbacks).
2. Official circulars: for up to 5 official sites (3 state electricity regulators, one oil company, one dairy co-op): Tavily Map then Crawl with instructions="find price circulars or tariff orders published in <month>", select_paths, extract_depth="advanced", limit ≤ 30, allow_external=False.
3. Evidence chasing: when an event is verified, ≤2 follow-up searches (same change by other sellers/states; the official circular). Store parent/child call ids so the app can draw the chase as a tree.
4. Attribution per month: prediction and coverage with vs without Tavily evidence → results/tavily_attribution.csv.
5. Tavily report card → results/tavily_report_card.md: calls, credits per prediction (include_usage), share of results inside the date window, share of quotes verified, share of events confirmed by 2 sources, median latency, fallback count, honest notes on what failed.
6. Package the event layer as `price_change_radar.py` with `find_price_changes(item, start_date, end_date)` + an MCP tool wrapper + short README.

## Prompt 3 — predictor and replay (22 Oct) → GO / NO-GO

1. Carve-out aggregation with `cpi_math.build_components` / `predict_headline`: tracked items move only their own weight; residuals and untracked subgroups follow B2 trend. YoY at the end, full precision.
2. Coverage (`cpi_math.coverage`) and contributions (`cpi_math.contributions_yoy`) every month.
3. Replay Jan–Sep 2026 in three versions, same cutoff and scoring: (a) trend only, (b) spine only, (c) spine + Tavily evidence. Strict vs exploratory tiers reported separately.
4. Range: 80% empirical interval from replay misses + "actual inside range in N of 9 months".
5. Skeptic: per month, top 3 contributors → one counter-search; ≥2 verified contrary quotes → widen range 50% and record why.
6. Scoreboard: mean absolute miss + direction hit-rate for (a),(b),(c),B1, poll (dated months). Per-month table.
7. GO only if (c) beats B1 and (a) on mean miss. Always report (c) vs (b) honestly (accuracy change + coverage gain). No tuning on test months.

## Prompt 4 — the app (23–25 Oct)

Streamlit `app.py`, plain labels, "experimental nowcast" wording everywhere.
- Home: countdown to next MoSPI release ("scheduled 12 Nov 2026 (Thu); November data due 12 Dec, a Saturday, so likely Mon 14 Dec under MoSPI's next-working-day rule"); big number with range + "inside range in N of 9 replay months"; coverage meter; top 3 contributors (pp); Tavily attribution line; sealed fingerprint, git tag, UTC time; "Try to prove this wrong" (Skeptic, live with cached fallback); "Run now" (event layer, last 7 days, ≤ ~20 credits, daily cap of 2 runs, shows "N live scans left today", cached fallback labelled with its timestamp); a receipt after each run: Tavily calls, credits, seconds; Nemotron calls.
- Evidence: table of every quote/event (item, price, place, date, exact line, link), spine vs Tavily; failed sources listed openly.
- Replay: three-way scoreboard vs B1 and poll; predicted vs actual chart; one miss explained.
- Tavily Flight Recorder: timestamped log from logs/flight_recorder.jsonl; one item end-to-end trace; the evidence chase as a tree; credits.
- Archive: sealed predictions with JSON, SHA-256, git tag, manifest link, official number when released, miss.
- Reporter brief (download): What moved / What we observed / What's uncertain — large model, computed numbers + verified quotes only, must state coverage and range.

## Prompt 5 — seal and November (26 Oct)

1. `seal.py` already exists: add a CLI `python seal_month.py 2026-10` that writes sealed/<month>.json (+ manifest path, code commit, model IDs, weights file hash, cutoff time UTC) and .sha256, commits, tags `seal-<month>`, pushes. Run for October on 29 Oct with evidence to 28 Oct.
2. Tag `submission-v1.0` before submitting; after it, prompts, weights, item list, source rules and scoring must not change.
3. November: run the nowcast manually each Monday (or a weekly GitHub Action if time allows), append-only to branch "live"; seal November on 10 Dec (release likely Mon 14 Dec, inside judging). Keys only in secrets.
4. `score.py`: after a release I enter the official figure in data/official_releases.csv → archive gets miss, inside-range, main surprise.
5. verify.md: how anyone recomputes the SHA-256 and checks the tag date.

## Prompt 6 — README, deploy, Devpost (27 Oct)

1. Confirm .env and keys are not in git history. 2. Deploy to Streamlit Community Cloud, keys in secrets, public URL, free and live until 15 Dec 12:00 PT. 3. README: one-liner, 8-step how it works, pipeline diagram (which Tavily endpoint does which job), replay scoreboard, Tavily report card, seals, honest limits, MIT licence, testing instructions incl. the daily cap. 4. Draft the Devpost write-up + "Why Tavily" + required Nebius/NVIDIA feedback. Claims only what the replay shows.
