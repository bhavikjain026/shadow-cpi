# Shadow CPI

**Shadow CPI predicts India's official CPI inflation before it's published, from live web evidence, with every
number cited, and seals each call in public before release.**

**Live app:** https://shadow-cpi.streamlit.app · **Demo video:** [TBD] · **Devpost:** [TBD]

**Result.** Jan–Sep 2026 replay: Shadow CPI missed by 0.194 percentage points on average; on the 6 months with an
economists' poll, 0.150 vs the poll's 0.148 (about a tie). ([`results/score_lock.json`](results/score_lock.json))

**Independent audit.** 12 events independently audited (AI-assisted search). Browser check of every source page:
9 quotes verbatim, 1 paywalled, 2 unreachable (**UNVERIFIED: tally reported by Eshan, per-row evidence not in repo**; [`audit/quote_check.md`](audit/quote_check.md)). Verdicts:
5 correct, 3 partly, 3 wrong, 1 unclear. Confirmed by another outlet: **9 of 12** (audit, other outlets). Confirmed
by Tavily's own evidence chase: **5 of 12** (before the fixes) and **4 of 9** (after them). The audit led to four
general bug fixes, logged with scores before and after: retail prices only (dropped a wholesale milk event), the
CPI's regular fuel grade (dropped a premium-fuel event), national vs regional scope (re-weighted a one-line rail fare
rise to its state) and no double counting (merged two Madhya Pradesh milk events into one). That took the replay
from 12 events to 9. ([`audit/event_audit.md`](audit/event_audit.md),
[`docs/after_scoring_changes.md`](docs/after_scoring_changes.md))

**Recall.** Of 29 known retail price changes in Jan–Sep 2026, the pipeline found 9 directly, and 14 including the
official price series it reads (Indian Oil Corporation (IOCL) LPG prices, the Petroleum Planning & Analysis Cell
(PPAC) petrol prices). ([`audit/missed_events.md`](audit/missed_events.md))

## How NVIDIA Nemotron and Nebius Token Factory are used

Nemotron only **extracts**: it points to a numbered line on a page, code copies that exact line and checks the number
is in it. A model never writes a quote, never picks a number and never picks a weight.

| Model ID (Token Factory) | Job | Calls sent (including cache hits) |
|---|---|---|
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Gatekeeper: "does this page state an Indian price or an announced price change?" (yes/no) | 622 (4,829) |
| `nvidia/nemotron-3-super-120b-a12b` | Reads a page and lists price quotes and price changes, each citing a numbered line; reads the skeptic's counter-search snippets | 719 (5,177) |

Calls sent = calls that reached Token Factory; in brackets, the total including cache hits (re-runs served free from the cache), from the flight recorder ([`results/app/flight_recorder.jsonl`](results/app/flight_recorder.jsonl)).
Token Factory is called at
[`shadow_cpi/nemotron.py` line 69](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/nemotron.py#L69)
(`POST /chat/completions` with a JSON schema; plain-JSON fallback on line 78), base URL in
[`shadow_cpi/settings.py` line 8](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/settings.py#L8).

## How Tavily is used

Tavily brings in the web news pages and the official price pages (IBJA, IOCL, PPAC); every call is cached and
logged in the flight recorder. All Tavily requests go through one function,
[`shadow_cpi/tavily.py` line 26](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/tavily.py#L26).

| Endpoint | Job | Where |
|---|---|---|
| **Search**, dates locked | News search with `start_date`/`end_date` = the target month plus a 10-day pre-window (the last 10 days of the previous month, for announcements), English and Hindi news preferred; code re-checks each page's date and drops pages that state the official figure | [`evidence.py` L258](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L258) |
| **Extract** | Reads the top dated pages with query-focused chunks; reads the India Bullion and Jewellers Association (IBJA) daily gold/silver report PDFs, IOCL's LPG price list and PPAC's petrol prices | [`evidence.py` L280](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L280), [L522](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/evidence.py#L522) |
| **Map + Crawl** (trial) | Trialled on 11 official/dairy sites to find price circulars and tariff orders; returned nothing usable. Reported, not used | [`tools/prompt_t.py` L65](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/tools/prompt_t.py#L65) |
| **Search** (evidence chase) | Up to 2 follow-up searches per verified event: the same change elsewhere, and the official notice | [`tools/prompt_t.py` L316](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/tools/prompt_t.py#L316) |
| **GET /usage** (guard) | Before every live run in the app: refuse below 150 credits left, or if the check fails | [`tavily.py` L70](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/tavily.py#L70), [`live_run.py` L68](https://github.com/bhavikjain026/shadow-cpi/blob/9345bdc034f066490c8679bff18d66f296bcbe3a/shadow_cpi/live_run.py#L68) |

Measured in [`results/tavily_report_card.md`](results/tavily_report_card.md) (22 Oct): 930 Tavily calls sent, 817
credits used (of a 1,000-credit monthly plan plus 3,125 add-on credits), 76% of dated search results inside the
requested window.
Three sources do not come through Tavily, and each is logged as a direct download: the Ministry of Statistics and
Programme Implementation (MoSPI) API for the official indices and weights; the Department of Consumer Affairs (DoCA)
daily food prices, downloaded by hand from behind a CAPTCHA; and Wayback Machine CDX lookups, used only by the date
test to date pages independently.

Web news quotes ran in full only for March 2026 (the test month). The other replay months used IBJA, IOCL and PPAC
prices read with Tavily Extract, DoCA food prices, and announced price-change events found with Tavily Search.

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
    FOOD["Government retail food prices (DoCA, by hand)"] --> C
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

## Honest limits

Nine test months is a small sample; the 80% range held the official figure in only 5 of 9 replay months; about
14–21% of the basket is measured each month and the rest is assumed to follow its recent trend; web news quotes ran
in full only for March; the June event (a 10% Uttar Pradesh electricity surcharge, later put on hold) is inside the
score; replays search today's web with date filters. All of it, plainly: [`docs/honest_limits.md`](docs/honest_limits.md). Rules and every change after
scoring: [`docs/frozen_rules.md`](docs/frozen_rules.md), [`docs/after_scoring_changes.md`](docs/after_scoring_changes.md).

## Licence

MIT ([`LICENSE`](LICENSE)). Built for the Nebius × NVIDIA Global AI Hackathon, 2026.
