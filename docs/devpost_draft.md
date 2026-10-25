# Shadow CPI: Devpost write-up (DRAFT)

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily.
> Numbers come from the results files named next to them. Only the October number, its fingerprint and the
> feedback section are left as `[I fill in]`. Claim only what the replay shows.

## One-liner
An experimental, sealed nowcast of India's next official CPI inflation number. It is made before MoSPI releases the number, has a source behind every input, is locked in public, and is scored when the real number comes out.

## Inspiration
India's CPI comes out once a month, about two weeks after the month ends. Until then, reporters, households and small businesses only have hunches and a handful of economists' polls. Meanwhile the web is full of real price evidence, if you can find it, date it and check it: market prices, dairy price hikes, LPG revisions and electricity tariff orders. MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web.

## What it does
- Shows an **experimental nowcast** of the coming month's CPI inflation (year-on-year), with an 80% range and the chance that the headline is 6.0% or more (the RBI's projection for Oct–Dec 2026).
- Says how often the official figure landed inside the range in the replay: 5 of 9 months (out-of-sample, leave-one-out ranges; `results/score_lock.json`). That is below the 80% target, so for the live months the range was widened after scoring: the prediction ± 0.284 percentage points, the 80th percentile of the 9 replay misses ignoring their sign (`docs/after_scoring_changes.md`).
- Shows **coverage**: how much of the basket was actually measured this month and how much is assumed to follow its recent trend: in the replay, 14–21% of the basket was measured each month (11% from government food prices alone), and the rest followed its trend (`results/replay.csv`).
- Lists every quote and announced price change behind the number, each with the exact line from the source page and a link.
- **Seals** the prediction before the release, as canonical JSON with a SHA-256 fingerprint and a git tag. Anyone can check that it was not changed afterwards (`verify.md`).
- After the release, the scoring script is run and the result is published: the miss, whether the figure was inside the range, and the main surprise.
- A skeptic counter-search looks for evidence against the top contributors each month, and widens the range by half if it finds 2 or more verified contrary quotes (it did in 1 of 9 replay months, January).
- A downloadable reporter brief with three parts: what moved, what we observed, and what's uncertain. It is written by code from computed numbers and verified quotes; the app shows an example from the September replay, labelled as such.

## How it works (8 steps)
1. **Official data:** the Ministry of Statistics and Programme Implementation (MoSPI) 2024-series All-India indices and weights, from MoSPI's API (a logged direct download). The code refuses to run with 2012-series weights.
2. **Government food prices:** Department of Consumer Affairs (DoCA) retail prices for the tracked foods, as monthly averages. The report sits behind a CAPTCHA, so it is downloaded by hand and saved in the repository.
3. **Tavily Search + Extract** find dated price quotes in English and Hindi news. Web news quotes ran in full only for March 2026; the other replay months used IBJA/IOCL/PPAC prices via Tavily Extract, DoCA food prices (manual CAPTCHA download) and announced-change events.
4. **Event layer:** Tavily searches for announced price changes with effective dates (milk, electricity, mobile tariffs, rail fares, medicines, school fees, GST, fuel), with a 10-day pre-window (the last 10 days of the previous month) to catch announcements. Map + Crawl was trialled on 11 official/dairy sites and returned nothing usable; the evidence chase of each verified change is reported, not used in the number.
5. **Gold and silver** are observed daily from the India Bullion and Jewellers Association (IBJA) daily report PDFs, LPG from Indian Oil Corporation's (IOCL) official price list, and petrol from the Petroleum Planning & Analysis Cell (PPAC), all read with Tavily Extract.
6. **Nemotron extracts only:** it cites a numbered line, and code takes that exact line and checks the number is in it. A model never writes a quote, never picks a number and never picks a weight.
7. **Code decides:** tracked items move only their own weight. Index levels are combined with the official weights, and year-on-year is computed last, at full precision. The range comes from replay misses.
8. **Seal, publish, score:** seal before the release, show everything in the app, and score after the release.

See `docs/pipeline.md` for the diagram.

## Replay results (January to September 2026; rules frozen before scoring, only logged bug fixes after)

| Method | Mean absolute miss (pp) | Direction right |
| --- | --- | --- |
| (a) Trend only | 0.212 | 8 of 9 |
| (b) Government food prices only | 0.225 | 9 of 9 |
| (c) Government food prices + Tavily evidence | **0.194** (0.185 before the audit's bug fixes) | 7 of 9 (8 before) |
| B1: last month's rate | 0.468 | 0 of 9 (it always predicts no change) |
| Economists' poll (6 dated months) | 0.148 (on the same 6 months, (c) 0.150; 0.138 before the fixes) | 6 of 6 |

Go / no-go: **GO** under the rule registered before scoring ((c) must beat B1 (0.468) and trend-only (0.212) on mean absolute miss). (c) vs (b), stated honestly: accuracy improved by 0.031 pp (0.225 → 0.194), better in 6 of 9 months; coverage rose from 11% to 14–21% of the basket. Government food prices on their own (b) did slightly worse than trend-only (a). Scored once, then re-scored once after logged bug fixes found by an independent audit (`docs/after_scoring_changes.md` §4); the June event, a 10% Uttar Pradesh electricity surcharge that was later put on hold, is inside the score; see `results/scoreboard.md` and `docs/preregistration.md`. All numbers in this table: `results/score_lock.json`.

**Independent audit:** 12 events independently audited (AI-assisted search). Source pages then opened in a browser (2026-10-25): 10 quotes verbatim (9 in the article text, 1 in the page title only), 1 paywalled, 1 not checked (the browser refuses Times of India) (`audit/quote_check.md`). Verdicts: 5 correct, 3 partly, 3 wrong, 1 unclear; confirmed by another outlet: 9 of 12 (audit, other outlets; `audit/event_audit.md`). The four general bug fixes that followed (retail only, the CPI fuel grade, national vs regional scope, no double counting) dropped 2 events and merged 2 into 1, taking the replay from 12 events to 9.

**Recall:** of 29 known retail price changes in Jan–Sep 2026, the pipeline found 9 directly, and 14 including the official price series it reads (IOCL LPG, PPAC petrol) (`audit/missed_events.md`).

**Sealed calls:** The October call is sealed at tag seal-2026-10 before submission; the scoring script is run when MoSPI publishes on 12 Nov. The November call will be sealed with the same frozen code at tag seal-2026-11 by 3 Dec, and scored the same way when November CPI is released (expected 14 Dec, inside judging).

## Why Tavily
- **It brings in the web pages.** News pages and the IBJA, IOCL and PPAC price pages come in through Tavily and are logged in the flight recorder. Three direct sources, each logged: the MoSPI API (official indices), the Consumer Affairs CAPTCHA download (food prices, by hand), and Wayback Machine CDX lookups (date test only).
- **Date windows make a nowcast possible.** Search with `start_date`/`end_date` = the target month, plus our own date check, lets us replay past months and drop anything outside the window.
- **Indian and Hindi news.** `include_domains` with `include_domains_mode="prefer"` steers searches to Indian English and Hindi publishers without excluding everything else.
- **Extract with query-focused chunks** returns just the passages that hold prices. That keeps the model's job small, and the line-by-line check strict.
- **Map + Crawl, tried honestly:** trialled on 11 official/dairy sites to find price circulars and tariff orders; returned nothing usable. The app's Tavily trace page lists each failure.
- **Evidence chasing:** each verified event gets up to 2 follow-up searches; 5 of 12 replay events (Tavily chase, before the audit's fixes) found a confirming result on another site (report only).
- **Measured, not claimed.** The Tavily report card (`results/tavily_report_card.md`) gives:
  - calls: 1,888 Tavily calls sent (cached repeats and free balance checks not counted); 1,809 credits used, of a 1,000-credit monthly plan plus 3,125 add-on credits from the Nebius builder program (as of 25 Oct 2026)
  - credits per replay prediction: 40.3 on average (event searches and the skeptic, 9 months)
  - share of dated search results inside the requested window: 78% (5,160 of 6,592; as of 25 Oct 2026)
  - share of quotes verified: 91 of 93 (March 2026 test; the number must appear in the cited line)
  - share of events confirmed by 2 sources: 4 of 9 replay events (after the audit's fixes)
  - median latency: 4.1 s per Tavily call (as of 25 Oct 2026)
  - direct downloads, logged: 154 calls (MoSPI's API, the CAPTCHA-gated DoCA food prices downloaded by hand, and failed Extracts)
- **Attribution:** the nowcast with vs without Tavily evidence, each month (`results/tavily_attribution.csv`): Tavily evidence lowered the mean miss from 0.225 to 0.194 pp and was closer in 6 of 9 months (after the audit's bug fixes).

## How we built it
- Python, standard library only for the core (no heavy frameworks). The app is built with Streamlit.
- Tavily (Search and Extract; Map and Crawl trialled) for news and official price pages; MoSPI's API, the DoCA CAPTCHA download and Wayback CDX lookups are the logged direct sources.
- NVIDIA Nemotron on Nebius Token Factory, used for extraction only:
  - `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` as a cheap yes/no gatekeeper (622 calls sent; 4,829 including cache hits)
  - `nvidia/nemotron-3-super-120b-a12b` for price quotes, price events and the skeptic's reads (719 calls sent; 5,177 including cache hits)
- One Recorder for every outside call: it caches each response (re-runs cost nothing) and keeps a flight-recorder log.
- Sealing: canonical JSON + SHA-256 + a `seal-<month>` git tag.

## Challenges we ran into
- The government daily price site blocks Tavily and sits behind a CAPTCHA, so DoCA food prices are downloaded by hand and saved in the repository (no automated web call is made for them).
- Some official pages are scanned PDFs with no text.
- Dates: a page's published date is not always its real date, so we check the page address and the text too.
- Leak guard: when replaying past months, pages that state the official figure for that month must be dropped.
- MoSPI's "gold" and "LPG" items are composites (jewellery; LPG + piped gas), so observing a price is not the same as observing the item.

More in `docs/honest_limits.md`.

## Accomplishments we're proud of
- No model ever chooses a number. Every quote in the app is an exact line from a source, and its number is checked.
- A public, verifiable seal for October 2026 before the 12 Nov release: [I fill in: October number], SHA-256 [I fill in], tag `seal-2026-10`.
- The flight recorder: every call, its credits and its latency, with the evidence chase drawn as a tree.

## What we learned
[I fill in: only claims the replay supports.]

## What's next
- Score the October seal on 12 Nov, and seal November before its release (likely Mon 14 Dec, inside judging).
- A weekly automated run, more items, Hindi price quotes at scale, and mandi early warning.

## Nebius and NVIDIA feedback
Every point below is a dated entry in `FEEDBACK_NOTES.md`, with its evidence (flight-recorder ids or a committed file).

- **What worked well:** JSON-schema output worked on the first call (`checks.py`). Citing line numbers instead of copying text made Hindi work: 59 of 62 Hindi quotes (95.2%) passed the "number is in the cited line" check, against 117 of 117 English quotes, on the March 2026 test.
- **What was hard:** the small model (Nano) answered "no" to a page that plainly listed Indian rupee prices, so code now never skips a page with a visible ₹ price. The extraction model (Super) sometimes named the item from the page's context rather than the cited line (onion for a potato line), took the low end of price ranges, or took the old price in "from X to Y"; all are now handled in code. A 180-second read timeout (20 Oct) and a connection reset (22 Oct) each stopped a run once; our HTTP helper now retries timeouts.
- **Model sizes:** Nano (30B) as the yes/no gatekeeper and Super (120B) for reading pages and writing search plans were enough; the extraction job is small because the model only points to a line and code checks it.
- **Cost and latency:** 1,341 Nemotron calls sent (10,006 including cache hits), median 1.6 s per call sent (flight recorder).
- **Requests for the platform:** consistent model IDs in `/models` (mixed case, `3.5` vs `3_5`); a documented retry policy for resets and timeouts on long runs.

## Tavily feedback

- **auto_parameters with no dates chose recent windows** (undocumented): w 57, d 14, m 1 of 72 pre-registered searches; 620 of 659 results were dated Oct 2026 and 38 undated, so a historical month found 0 of 29 known changes. A time-locked search needs explicit `start_date`/`end_date`.
- **Map returns 0 silently** (undocumented): on 4 government/PSU sites (merc.gov.in, derc.gov.in, uperc.org, iocl.com) and 3 of 6 dairy sites, Map came back with `results: []`, no `failed_results` and no error, with and without `instructions`; an empty answer cannot be told apart from "blocked". A bad start address, by contrast, got a clear HTTP 400.
- **Scanned PDFs return only the letterhead** (undocumented): Gokul's rate-list PDF (effective 11 Aug 2026) came back as 607 characters of letterhead with basic and with advanced Extract; the advanced call cost 1 credit.
- **An Extract where every URL failed was still charged**: 14 such calls each cost 1 credit, while empty Map/Crawl calls (16) cost 0.
- **`/usage` lagged for a day** (it reported 6 credits used all day on 20 Oct while per-call counts reached 226), so we budget from per-call `include_usage`.
- **`include_domains_mode="prefer"` let many off-target results through** (Reuters polls on other countries; New York fare news for a Hindi bus-fare query).

## Try it
- App: https://shadow-cpi.streamlit.app
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
