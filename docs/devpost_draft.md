# Shadow CPI: Devpost write-up (DRAFT)

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily.
> Every `[TBD: from replay]` must be filled from `results/` before submitting. Claim only what the replay shows.

## One-liner
An experimental, sealed nowcast of India's next official CPI inflation number. It is made before MoSPI releases the number, has a source behind every input, is locked in public, and is scored when the real number comes out.

## Inspiration
India's CPI comes out once a month, about two weeks after the month ends. Until then, reporters, households and small businesses only have hunches and a handful of economists' polls. Meanwhile the web is full of real price evidence, if you can find it, date it and check it: market prices, dairy price hikes, LPG revisions and electricity tariff orders. MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web.

## What it does
- Shows an **experimental nowcast** of the coming month's CPI inflation (year-on-year), with an 80% range taken from the replay misses: about −0.14 / +0.33 percentage points around the nowcast (10th–90th percentile of the 9 replay misses).
- Says how often the official figure landed inside that range in the replay: 5 of 9 months (out-of-sample, leave-one-out ranges). That is below the 80% target, so the range is too narrow.
- Shows **coverage**: how much of the basket was actually measured this month and how much is carried on trend: in the replay, 14–21% of the basket was measured each month (11% from the government spine alone), and the rest was carried on trend.
- Lists every quote and announced price change behind the number, each with the exact line from the source page and a link.
- **Seals** the prediction before the release, as canonical JSON with a SHA-256 fingerprint and a git tag. Anyone can check that it was not changed afterwards (`verify.md`).
- After the release, scores itself in public: the miss, whether the figure was inside the range, and the main surprise.
- "Try to prove this wrong": the skeptic searches for evidence against the top contributors, and it widens the range if it finds verified contrary quotes.
- A downloadable reporter brief with three parts: what moved, what we observed, and what's uncertain.

## How it works (8 steps)
1. **Official data:** MoSPI's 2024-series All-India indices and weights. The code refuses to run with 2012-series weights.
2. **Government price spine:** Department of Consumer Affairs retail prices for the tracked foods, as monthly averages. The report sits behind a CAPTCHA, so it is downloaded by hand and saved in the repository.
3. **Tavily Search + Extract** find dated price quotes in English and Hindi news for items the spine lacks.
4. **Event layer:** Tavily searches for announced price changes with effective dates (milk, LPG, electricity, mobile tariffs, rail fares, medicines, school fees, GST). Tavily Map + Crawl read official circulars, and evidence chasing confirms each change with a second source.
5. **Gold and silver** are observed daily from IBJA's daily bullion-report PDFs, and LPG from IOCL's official price list, both read with Tavily Extract.
6. **Nemotron extracts only:** it cites a numbered line, and code takes that exact line and checks the number is in it. A model never writes a quote, never picks a number and never picks a weight.
7. **Code decides:** tracked items move only their own weight. Index levels are combined with the official weights, and year-on-year is computed last, at full precision. The range comes from replay misses.
8. **Seal, publish, score:** seal before the release, show everything in the app, and score after the release.

See `docs/pipeline.md` for the diagram.

## Replay results (January to September 2026, test months never used for tuning)

| Method | Mean absolute miss (pp) | Direction right |
| --- | --- | --- |
| (a) Trend only | 0.212 | 8 of 9 |
| (b) Government price spine only | 0.225 | 9 of 9 |
| (c) Spine + Tavily evidence | **0.194** (0.185 before the Amendment 3 bug fixes) | 7 of 9 (8 before) |
| B1: last month's rate | 0.47 (from `results/baselines.csv`) | n/a |
| Economists' poll (6 dated months) | 0.148 (on the same 6 months, (c) 0.150; 0.138 before the fixes) | 6 of 6 |

Go / no-go: **GO** under the rule registered before scoring ((c) must beat B1 (0.468) and trend-only (0.212) on mean absolute miss). (c) vs (b), stated honestly: accuracy improved by 0.031 pp (0.225 → 0.194), better in 6 of 9 months; coverage rose from 11% to 14–21% of the basket. The spine on its own (b) did slightly worse than trend-only (a). Scored once, then re-scored once after logged bug fixes found by an independent audit (Amendment 3, `docs/after_scoring_changes.md`); see `results/scoreboard.md` and `docs/preregistration.md`.

## Why Tavily
- **It is the single entry point for web pages.** Every web page the nowcast uses (news, IBJA, IOCL, PPAC) comes in through Tavily and is logged in the flight recorder. Two exceptions, stated openly: MoSPI's official indices are a logged direct download from MoSPI's API, and the Consumer Affairs spine is downloaded by hand from behind a CAPTCHA.
- **Date windows make a nowcast possible.** Search with `start_date`/`end_date` = the target month, plus our own date check, lets us replay past months and drop anything outside the window.
- **Indian and Hindi news.** `include_domains` with `include_domains_mode="prefer"` steers searches to Indian English and Hindi publishers without excluding everything else.
- **Extract with query-focused chunks** returns just the passages that hold prices. That keeps the model's job small, and the line-by-line check strict.
- **Map + Crawl** reach official circulars (tariff orders, price circulars) that news may never cover.
- **Evidence chasing:** each verified event triggers up to 2 follow-up searches. The app draws these as a tree.
- **Event layer packaged for reuse:** `price_change_radar.py` exposes `find_price_changes(item, start_date, end_date)` and an MCP tool wrapper.
- **Measured, not claimed.** The Tavily report card (`results/tavily_report_card.md`) gives:
  - calls: 729 Tavily calls sent (cached repeats not counted); 222 dated searches for the test months
  - credits per prediction: about 52 (466 credits for the 9 replay months, including the skeptic)
  - share of results inside the date window: 74% (1,067 of 1,447 search results for the test months)
  - share of quotes verified: 91 of 93 (March 2026 test; the number must appear in the cited line)
  - share of events confirmed by 2 sources: 3 of 12 events in the test months
  - median latency: 4.3 s per Tavily call
  - fallback count: 1 Tavily-to-direct fallback (the Consumer Affairs dashboard). By design and logged: MoSPI's API (148 direct calls) and the CAPTCHA-gated spine (downloaded by hand, 5 requests)
- **Attribution:** the nowcast with vs without Tavily evidence, each month (`results/tavily_attribution.csv`): Tavily evidence lowered the mean miss from 0.225 to 0.194 pp and was closer in 6 of 9 months (after the Amendment 3 bug fixes).

## How we built it
- Python, standard library only for the core (no heavy frameworks). The app is built with Streamlit.
- Tavily (Search, Extract, Map, Crawl) for all web data.
- NVIDIA Nemotron on Nebius Token Factory, used for extraction only. There are three sizes:
  - a small model as a cheap yes/no gatekeeper
  - a mid model for price quotes and price events
  - a large model for the reporter brief's wording.
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
- A public, verifiable seal for October 2026 before the 12 Nov release: SHA-256 [TBD: from seal], tag `seal-2026-10`.
- The flight recorder: every call, its credits and its latency, with the evidence chase drawn as a tree.

## What we learned
[TBD: owner to write. Only claims the replay supports.]

## What's next
- Score the October seal on 12 Nov, and seal November before its release (likely Mon 14 Dec, inside judging).
- A weekly automated run, more items, Hindi price quotes at scale, and mandi early warning.

## Nebius and NVIDIA feedback
> Required section. Replace every prompt below with what actually happened. Do not keep a sentence that isn't true for us.

- **What worked well:** [TBD: owner, e.g. JSON-schema output, line-citation reliability, speed of the small gatekeeper model]
- **What was hard:** [TBD: owner, e.g. any model ID, JSON-mode or rate-limit issues met during checks.py]
- **Model sizes:** [TBD: owner, how the small / mid / large split worked in practice, and where a bigger model did or did not help]
- **Cost and latency:** 1,341 Nemotron calls sent (cached repeats not counted), median 1.6 s each (flight recorder).
- **Requests for the platform:** [TBD: owner]

## Try it
- App: [TBD: public URL]
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
