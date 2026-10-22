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
- Says how often the official figure landed inside the range in the replay: 5 of 9 months (out-of-sample, leave-one-out ranges; `results/score_lock.json`). That is below the 80% target, so for the live months the range was widened after scoring (Amendment 2): the prediction ± 0.28 percentage points, the 80th percentile of the 9 replay misses ignoring their sign (`docs/after_scoring_changes.md`).
- Shows **coverage**: how much of the basket was actually measured this month and how much is carried on trend: in the replay, 14–21% of the basket was measured each month (11% from the government spine alone), and the rest was carried on trend (`results/replay.csv`).
- Lists every quote and announced price change behind the number, each with the exact line from the source page and a link.
- **Seals** the prediction before the release, as canonical JSON with a SHA-256 fingerprint and a git tag. Anyone can check that it was not changed afterwards (`verify.md`).
- After the release, scores itself in public: the miss, whether the figure was inside the range, and the main surprise.
- A skeptic counter-search looks for evidence against the top contributors each month, and widens the range by half if it finds 2 or more verified contrary quotes (it did in 1 of 9 replay months, January).
- A downloadable reporter brief with three parts: what moved, what we observed, and what's uncertain. It is written by code from computed numbers and verified quotes; the app shows an example from the September replay, labelled as such.

## How it works (8 steps)
1. **Official data:** MoSPI's 2024-series All-India indices and weights. The code refuses to run with 2012-series weights.
2. **Government price spine:** Department of Consumer Affairs retail prices for the tracked foods, as monthly averages. The report sits behind a CAPTCHA, so it is downloaded by hand and saved in the repository.
3. **Tavily Search + Extract** find dated price quotes in English and Hindi news (in full for the March 2026 test; other replay months skipped web quotes to save credits).
4. **Event layer:** Tavily searches for announced price changes with effective dates (milk, electricity, mobile tariffs, rail fares, medicines, school fees, GST, fuel). We also tried Tavily Map + Crawl on official and dairy sites, and an evidence chase of each verified change; both are reported, not used in the number.
5. **Gold and silver** are observed daily from IBJA's daily bullion-report PDFs, and LPG from IOCL's official price list, both read with Tavily Extract.
6. **Nemotron extracts only:** it cites a numbered line, and code takes that exact line and checks the number is in it. A model never writes a quote, never picks a number and never picks a weight.
7. **Code decides:** tracked items move only their own weight. Index levels are combined with the official weights, and year-on-year is computed last, at full precision. The range comes from replay misses.
8. **Seal, publish, score:** seal before the release, show everything in the app, and score after the release.

See `docs/pipeline.md` for the diagram.

## Replay results (January to September 2026; rules frozen before scoring, only logged bug fixes after)

| Method | Mean absolute miss (pp) | Direction right |
| --- | --- | --- |
| (a) Trend only | 0.212 | 8 of 9 |
| (b) Government price spine only | 0.225 | 9 of 9 |
| (c) Spine + Tavily evidence | **0.194** (0.185 before the Amendment 3 bug fixes) | 7 of 9 (8 before) |
| B1: last month's rate | 0.468 | 0 of 9 (it always predicts no change) |
| Economists' poll (6 dated months) | 0.148 (on the same 6 months, (c) 0.150; 0.138 before the fixes) | 6 of 6 |

Go / no-go: **GO** under the rule registered before scoring ((c) must beat B1 (0.468) and trend-only (0.212) on mean absolute miss). (c) vs (b), stated honestly: accuracy improved by 0.031 pp (0.225 → 0.194), better in 6 of 9 months; coverage rose from 11% to 14–21% of the basket. The spine on its own (b) did slightly worse than trend-only (a). Scored once, then re-scored once after logged bug fixes found by an independent audit (Amendment 3, `docs/after_scoring_changes.md`); see `results/scoreboard.md` and `docs/preregistration.md`. All numbers in this table: `results/score_lock.json`.

**Independent audit:** 12 events checked by hand: 5 correct, 3 partly, 3 wrong, 1 unclear; 9 confirmed by a second source (`audit/event_audit.md`). The four general bug fixes that followed (retail only, the CPI fuel grade, national vs regional scope, no double counting) took the replay from 12 events to 9.

**Recall:** of 29 known retail price changes in Jan–Sep 2026, the pipeline found 9 directly, and 14 including the official price series it reads (IOCL LPG, PPAC petrol) (`audit/missed_events.md`).

**Sealed calls:** The October call is sealed at tag seal-2026-10 before submission and scores itself when MoSPI publishes on 12 Nov. The November call will be sealed with the same frozen code at tag seal-2026-11 by 3 Dec, and scores itself when November CPI is released (expected 14 Dec, inside judging).

## Why Tavily
- **It is the single entry point for web pages.** Every web page the nowcast uses (news, IBJA, IOCL, PPAC) comes in through Tavily and is logged in the flight recorder. Two exceptions, stated openly: MoSPI's official indices are a logged direct download from MoSPI's API, and the Consumer Affairs spine is downloaded by hand from behind a CAPTCHA.
- **Date windows make a nowcast possible.** Search with `start_date`/`end_date` = the target month, plus our own date check, lets us replay past months and drop anything outside the window.
- **Indian and Hindi news.** `include_domains` with `include_domains_mode="prefer"` steers searches to Indian English and Hindi publishers without excluding everything else.
- **Extract with query-focused chunks** returns just the passages that hold prices. That keeps the model's job small, and the line-by-line check strict.
- **Map + Crawl, tried honestly:** we pointed Map + Crawl at 5 official sites and 6 dairy sites to find price circulars and tariff orders. Map returned nothing on the government and PSU sites, and some rate lists are image-only PDFs; the app's Tavily trace page lists each failure.
- **Evidence chasing:** each verified event gets up to 2 follow-up searches; 5 of 12 replay events found a confirming result on another site (report only).
- **Measured, not claimed.** The Tavily report card (`results/tavily_report_card.md`) gives:
  - calls: 930 Tavily calls sent (cached repeats and free balance checks not counted); 817 credits used, of a 1,000-credit monthly plan plus 3,125 add-on credits from the Nebius builder program (report card, 22 Oct)
  - credits per replay prediction: 40.3 on average (event searches and the skeptic, 9 months)
  - share of dated search results inside the requested window: 76% (2,415 of 3,194)
  - share of quotes verified: 91 of 93 (March 2026 test; the number must appear in the cited line)
  - share of events confirmed by 2 sources: 4 of 9 replay events
  - median latency: 4.2 s per Tavily call
  - direct downloads, logged: 154 calls (MoSPI's API, the CAPTCHA-gated spine downloaded by hand, and failed Extracts)
- **Attribution:** the nowcast with vs without Tavily evidence, each month (`results/tavily_attribution.csv`): Tavily evidence lowered the mean miss from 0.225 to 0.194 pp and was closer in 6 of 9 months (after the Amendment 3 bug fixes).

## How we built it
- Python, standard library only for the core (no heavy frameworks). The app is built with Streamlit.
- Tavily (Search, Extract, Map, Crawl) for all web data.
- NVIDIA Nemotron on Nebius Token Factory, used for extraction only:
  - `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` as a cheap yes/no gatekeeper (622 calls sent; 4,829 including cache hits)
  - `nvidia/nemotron-3-super-120b-a12b` for price quotes, price events and the skeptic's reads (719 calls sent; 5,177 including cache hits)
  - a large model (`nvidia/Nemotron-3-Ultra-550b-a55b`) is configured but was not needed: the reporter brief is written by code.
- One Recorder for every outside call: it caches each response (re-runs cost nothing) and keeps a flight-recorder log.
- Sealing: canonical JSON + SHA-256 + a `seal-<month>` git tag.

## Challenges we ran into
- The government daily price site blocks Tavily and sits behind a CAPTCHA, so the spine is downloaded by hand and saved in the repository (no automated web call is made for it).
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
> Required section. Replace every prompt below with what actually happened. Do not keep a sentence that isn't true for us.

- **What worked well:** [I fill in]
- **What was hard:** [I fill in]
- **Model sizes:** [I fill in]
- **Cost and latency:** 1,341 Nemotron calls sent (10,006 including cache hits), median 1.6 s per call sent (flight recorder).
- **Requests for the platform:** [I fill in]

## Try it
- App: https://shadow-cpi.streamlit.app
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
