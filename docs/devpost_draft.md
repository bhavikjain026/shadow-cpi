# Shadow CPI: Devpost write-up (DRAFT)

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily.
> Every `[TBD: from replay]` must be filled from `results/` before submitting. Claim only what the replay shows.

## One-liner
An experimental, sealed nowcast of India's next official CPI inflation number. It is made before MoSPI releases the number, has a source behind every input, is locked in public, and is scored when the real number comes out.

## Inspiration
India's CPI comes out once a month, about two weeks after the month ends. Until then, reporters, households and small businesses only have hunches and a handful of economists' polls. Meanwhile the web is full of real price evidence, if you can find it, date it and check it: market prices, dairy price hikes, LPG revisions and electricity tariff orders. MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web.

## What it does
- Shows an **experimental nowcast** of the coming month's CPI inflation (year-on-year), with an 80% range: [TBD: from replay].
- Says how often the official figure landed inside that range in the replay: [TBD: from replay] of 9 months.
- Shows **coverage**: how much of the basket was actually measured this month and how much is carried on trend: [TBD: from replay].
- Lists every quote and announced price change behind the number, each with the exact line from the source page and a link.
- **Seals** the prediction before the release, as canonical JSON with a SHA-256 fingerprint and a git tag. Anyone can check that it was not changed afterwards (`verify.md`).
- After the release, scores itself in public: the miss, whether the figure was inside the range, and the main surprise.
- "Try to prove this wrong": the skeptic searches for evidence against the top contributors, and it widens the range if it finds verified contrary quotes.
- A downloadable reporter brief with three parts: what moved, what we observed, and what's uncertain.

## How it works (8 steps)
1. **Official data:** MoSPI's 2024-series All-India indices and weights. The code refuses to run with 2012-series weights.
2. **Government price spine:** daily retail prices for 38 foods, as centre-level monthly averages.
3. **Tavily Search + Extract** find dated price quotes in English and Hindi news for items the spine lacks.
4. **Event layer:** Tavily searches for announced price changes with effective dates (milk, LPG, electricity, mobile tariffs, rail fares, medicines, school fees, GST). Tavily Map + Crawl read official circulars, and evidence chasing confirms each change with a second source.
5. **Gold and silver** are observed daily from a published rate page that Tavily finds and extracts.
6. **Nemotron extracts only:** it cites a numbered line, and code takes that exact line and checks the number is in it. A model never writes a quote, never picks a number and never picks a weight.
7. **Code decides:** tracked items move only their own weight. Index levels are combined with the official weights, and year-on-year is computed last, at full precision. The range comes from replay misses.
8. **Seal, publish, score:** seal before the release, show everything in the app, and score after the release.

See `docs/pipeline.md` for the diagram.

## Replay results (January to September 2026, test months never used for tuning)

| Method | Mean absolute miss (pp) | Direction right |
| --- | --- | --- |
| (a) Trend only | [TBD: from replay] | [TBD: from replay] |
| (b) Government price spine only | [TBD: from replay] | [TBD: from replay] |
| (c) Spine + Tavily evidence | [TBD: from replay] | [TBD: from replay] |
| B1: last month's rate | 0.47 (from `results/baselines.csv`) | n/a |
| Economists' poll (6 dated months) | 0.15 (from `results/baselines.csv`) | [TBD: from replay] |

Go / no-go: [TBD: from replay]. (c) vs (b), stated honestly: accuracy change [TBD: from replay]; coverage gain [TBD: from replay].

## Why Tavily
- **It is the single entry point for web data.** Every web page the nowcast uses comes in through Tavily and is logged in the flight recorder. Direct downloads happen only as a counted fallback.
- **Date windows make a nowcast possible.** Search with `start_date`/`end_date` = the target month, plus our own date check, lets us replay past months and drop anything outside the window.
- **Indian and Hindi news.** `include_domains` with `include_domains_mode="prefer"` steers searches to Indian English and Hindi publishers without excluding everything else.
- **Extract with query-focused chunks** returns just the passages that hold prices. That keeps the model's job small, and the line-by-line check strict.
- **Map + Crawl** reach official circulars (tariff orders, price circulars) that news may never cover.
- **Evidence chasing:** each verified event triggers up to 2 follow-up searches. The app draws these as a tree.
- **Event layer packaged for reuse:** `price_change_radar.py` exposes `find_price_changes(item, start_date, end_date)` and an MCP tool wrapper.
- **Measured, not claimed.** The Tavily report card (`results/tavily_report_card.md`) gives:
  - calls: [TBD: from replay]
  - credits per prediction: [TBD: from replay]
  - share of results inside the date window: [TBD: from replay]
  - share of quotes verified: [TBD: from replay]
  - share of events confirmed by 2 sources: [TBD: from replay]
  - median latency: [TBD: from replay]
  - fallback count: [TBD: from replay]
- **Attribution:** the nowcast with vs without Tavily evidence, each month (`results/tavily_attribution.csv`): [TBD: from replay].

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
- The government daily price site blocks Tavily and sits behind a CAPTCHA, so the spine was downloaded by hand and logged as a fallback.
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
- **Cost and latency:** [TBD: from the flight recorder: Nemotron calls and median latency]
- **Requests for the platform:** [TBD: owner]

## Try it
- App: [TBD: public URL]
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
