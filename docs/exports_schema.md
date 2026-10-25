# Research exports: schema and coverage limits

Built by `python tools/export.py` (offline, 0 credits) from committed results files. Research tool, not investment
advice. Each file is a copy: if it disagrees with its source file, the source wins.

## exports/nowcast.csv — one row per month and model

| Column | Meaning |
|---|---|
| month | target month, YYYY-MM |
| model | `v1 (c)` (scored replay, `results/replay.csv`) or `v2 (experimental)` (`results/v2_score_lock.json`) |
| nowcast_yoy | predicted year-on-year CPI inflation, % |
| range_low, range_high | the month's 80% range, % (v1: leave-one-out; v2: its own rule) |
| official_yoy | MoSPI's published figure, % |
| inside_range | official figure inside the range (True/False) |
| measured_share | share of the basket measured that month (the rest follows its trend) |
| source | the file the row was copied from |

**Limits.** Replay months Jan–Sep 2026 only (9 months); the October call is in `sealed/` once sealed. Replays search
today's web with date filters, so they are easier than live conditions (`docs/honest_limits.md`).

## exports/evidence.csv — one row per verified claim

| Column | Meaning |
|---|---|
| source | `radar`, `v2 scored evidence`, or `arm A`…`arm H` (search-parameter tests, development data) |
| month, kind | target month; item kind (electricity, milk, lpg, diesel, petrol, metro, bus, rail, mobile) |
| change | the claim's price change as a fraction (0.05 = +5%), computed by code |
| effective_date | when the change takes effect, if stated |
| quote_short | the exact cited line, whitespace-collapsed, at most 200 characters (never the page's full text) |
| url, page_date | the page and its date (Tavily's, the address's or the page's own) |
| search_request_id, search_response_sha256 | Tavily's request id and the response hash, or `not logged` (runs before Amendment F) |
| seal | the seal or freeze that covers the row, or why there is none |

**Limits.** "Verified" means the number is in the cited line on a page dated inside the window. It does **not** mean
the claim moved the nowcast: scope rules (retail only, the CPI variety, geography, one event per kind × state × month)
drop some verified claims, e.g. foreign fares that passed the line check. Arms A–H are development data. Chain of
custody per row: the app's "Chain of custody" page.

## exports/radar.jsonl — one JSON object per October radar event

Fields: `kind`, `effective_date`, `states`, `change`, `tier` (`verified` / `corroborated`), `tavily_only`, `effect_pp`
(effect on October headline inflation, pp; null for items that move through an official series), `sources` (each:
`url`, `domain`, `published`, `quote_short`, `search_request_id`, `extract_request_id`).

**Limits.** Report-only; frozen at 29 Oct 2026 23:59 IST and scored afterwards against an independent list
(`v2/RADAR_PREREG.md`). Before the freeze the file can still grow.
