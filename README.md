# Shadow CPI

**Shadow CPI predicts India's official CPI inflation before it's published, from live web evidence, with every
number cited, and seals each call in public before release.**

**Live app:** https://shadow-cpi.streamlit.app · **Demo video:** [TBD] · **Devpost:** [TBD]

**Result.** Jan–Sep 2026 replay: Shadow CPI missed by 0.194 percentage points on average; on the 6 months with an
economists' poll, 0.150 vs the poll's 0.148 (about a tie). ([`results/score_lock.json`](results/score_lock.json))

**Independent audit.** 12 events checked by hand: 5 correct, 3 partly, 3 wrong, 1 unclear; 9 confirmed by a second
source. Four general bug fixes followed, logged with scores before and after.
([`audit/event_audit.md`](audit/event_audit.md), [`docs/after_scoring_changes.md`](docs/after_scoring_changes.md))

**Recall.** Of 29 known retail price changes in Jan–Sep 2026, the pipeline found 9 directly, and 14 including the
official price series it reads (IOCL LPG, PPAC petrol). ([`audit/missed_events.md`](audit/missed_events.md))

## How NVIDIA Nemotron and Nebius Token Factory are used

Nemotron only **extracts**: it points to a numbered line on a page, code copies that exact line and checks the number
is in it. A model never writes a quote, never picks a number and never picks a weight.

| Model ID (Token Factory) | Job | Calls sent (including cache hits) |
|---|---|---|
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Gatekeeper: "does this page state an Indian price or an announced price change?" (yes/no) | 622 (4,829) |
| `nvidia/nemotron-3-super-120b-a12b` | Reads a page and lists price quotes and price changes, each citing a numbered line; reads the skeptic's counter-search snippets | 719 (5,177) |
| `nvidia/Nemotron-3-Ultra-550b-a55b` | Configured in `config/models.json`, not used: the reporter brief is written by code | 0 (0) |

Calls sent = calls that reached Token Factory; in brackets, the total including cache hits (re-runs served free from the cache), from the flight recorder ([`results/app/flight_recorder.jsonl`](results/app/flight_recorder.jsonl)).
Token Factory is called at
[`shadow_cpi/nemotron.py` line 69](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/nemotron.py#L69)
(`POST /chat/completions` with a JSON schema; plain-JSON fallback on line 78), base URL in
[`shadow_cpi/settings.py` line 8](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/settings.py#L8).

## How Tavily is used

Every web page the nowcast uses comes in through Tavily, and every call is cached and logged in the flight recorder.
All requests go through one function,
[`shadow_cpi/tavily.py` line 26](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/tavily.py#L26).

| Endpoint | Job | Where |
|---|---|---|
| **Search**, dates locked | News search with `start_date`/`end_date` = the target month (plus 10 days before, for announcements), English and Hindi news preferred; code re-checks each page's date and drops pages that state the official figure | [`evidence.py` L258](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L258) |
| **Extract** | Reads the top dated pages with query-focused chunks; reads IBJA's daily gold/silver report PDFs, IOCL's LPG price list and PPAC's petrol prices | [`evidence.py` L280](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L280), [L522](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L522) |
| **Map + Crawl** (attempts) | Looked for price circulars and tariff orders on 5 official sites and 6 dairy sites. Map returned nothing on the government and PSU sites; reported, not used | [`tools/prompt_t.py` L65](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/tools/prompt_t.py#L65) |
| **Search** (evidence chase) | Up to 2 follow-up searches per verified event: the same change elsewhere, and the official notice | [`tools/prompt_t.py` L316](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/tools/prompt_t.py#L316) |
| **GET /usage** (guard) | Before every live run in the app: refuse below 150 credits left, or if the check fails | [`tavily.py` L70](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/tavily.py#L70), [`live_run.py` L68](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/live_run.py#L68) |

Measured in [`results/tavily_report_card.md`](results/tavily_report_card.md) (22 Oct): 930 Tavily calls sent, 817
credits used (of a 1,000-credit monthly plan plus 3,125 add-on credits), 76% of dated search results inside the
requested window.
Two sources do not come through Tavily, by design: MoSPI's official indices (a JSON API) and the government's daily food prices (behind a CAPTCHA, downloaded by
hand). Both are logged.

---

## Pipeline

```mermaid
flowchart TD
    NEWS["Indian news, English + Hindi"] --> S["Tavily Search<br/>date window = the month"]
    S --> X["Tavily Extract<br/>top dated pages"]
    OBS["IBJA gold/silver, IOCL LPG, PPAC petrol"] --> X2["Tavily Extract"]
    X --> G["Nemotron Nano: gatekeeper (yes/no)"]
    G -- yes --> M["Nemotron Super: quotes + price changes,<br/>each citing a numbered line"]
    M --> V["Code: copy the exact line,<br/>check the number is in it; dates + leak guard"]
    V --> R["Code: event rules (retail only, CPI variety,<br/>national vs regional, no double counting)"]
    SPINE["Government retail prices (DoCA, by hand)"] --> C
    MOSPI["MoSPI indices + 2024 weights (API)"] --> C
    X2 --> C
    R --> C["Code: carve-out by item weight, combine index LEVELS,<br/>year-on-year last, 80% range from replay misses"]
    C --> SEAL["Seal: canonical JSON + SHA-256 + git tag"]
    SEAL --> APP["App: Home, Evidence, Replay, Tavily trace, Flight Recorder, Archive"]
```

More detail, including every Tavily setting: [`docs/pipeline.md`](docs/pipeline.md).

## Run it locally

```bash
pip install -r requirements-app.txt
```
```bash
streamlit run app.py
```

The app reads the committed results files, so it needs no keys. The "Run live" button stays off unless
`RUN_LIVE_ENABLED` is set and both keys (`SCPI_TAVILY_API_KEY`, `SCPI_NEBIUS_API_KEY`) are in the environment.
Tests (no keys, no credits):

```bash
python -m pytest -q
```

To run the pipeline itself, copy `.env.example` to `.env`, add the two keys, and start with `python checks.py`.
Deployment: [`docs/deploy.md`](docs/deploy.md).

## The seal, and how to check it

Each month's call is written as canonical JSON with its SHA-256 fingerprint and tagged in git (`seal-2026-10`)
before MoSPI publishes. Anyone can download the file at the tag and recompute the fingerprint:
[`verify.md`](verify.md). After the release, the Archive page shows the miss and whether the official figure was
inside the range.

## For research teams

Shadow CPI is designed for research teams that need web evidence without **look-ahead bias**: a replay that quietly
uses a page published after its cutoff looks better than it could ever be live. Three tools help:

- **Exports** (`python tools/export.py`): `exports/nowcast.csv`, `exports/evidence.csv` (short cited lines only,
  never page text) and `exports/radar.jsonl`. Columns and coverage limits: [`docs/exports_schema.md`](docs/exports_schema.md).
- **`as_of(day)`** ([`v2/asof.py`](v2/asof.py), app page "As of a date"): the nowcast, evidence and coverage from items
  found on or before a day; a test proves nothing found later can appear.
- **Seal checks** ([`verify.md`](verify.md)) and the app's "Chain of custody" page: from any number to its quote, page,
  page date, Tavily request ID, response hash and seal.
- **Leak checker** ([`shadow_cpi/leakcheck.py`](shadow_cpi/leakcheck.py), example in
  [`examples/leakcheck_example.py`](examples/leakcheck_example.py)): label any search result safe / date_flag / leak
  against a cutoff; undated pages are flagged, not dropped.

Research tool, not investment advice.

## Beyond CPI

The same date discipline carries to other scheduled events. The second domain we tested is **finance**: replaying the
day before RBI policy decisions and large-company results, with and without Tavily's date fields
([`v2/FINANCE_PREREG.md`](v2/FINANCE_PREREG.md), results in [`results/finance_lookahead.md`](results/finance_lookahead.md)
and on the app's "Tavily field report" page). Designed for event studies and backtests that must not see the outcome
early. Research tool, not investment advice.

## Honest limits

Nine test months is a small sample; the 80% range held the official figure in only 5 of 9 replay months; about
14–21% of the basket is measured each month and the rest is carried on trend; replays search today's web with date
filters. All of it, plainly: [`docs/honest_limits.md`](docs/honest_limits.md). Rules and every change after
scoring: [`docs/frozen_rules.md`](docs/frozen_rules.md), [`docs/after_scoring_changes.md`](docs/after_scoring_changes.md).

## Licence

MIT ([`LICENSE`](LICENSE)). Built for the Nebius × NVIDIA Global AI Hackathon, 2026.
