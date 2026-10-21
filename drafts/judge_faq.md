# Judge FAQ (draft)

Short, plain answers for the Q&A. Each answer points to a file in the repo a judge can check. Placeholders in
[brackets] must be filled in from the results files before use. No number here is invented.

## 1. Why use AI agents and live web search instead of a regression on official data?

A regression on official data can only use what MoSPI has already published, so it ends up projecting the
recent trend. We do run that as a baseline (B2, "trend only"), and it is hard to beat. What a regression cannot see
is what changed *this* month: a milk co-op raising prices, a new electricity tariff order, a petrol price revision.
Those are announced publicly, often in Hindi or regional news, before MoSPI measures them. Web search finds them, the
model only pulls out the exact line, and plain code does every calculation. The gain over trend is real but modest,
so we report it next to the trend baseline rather than claiming a big win.

## 2. Why India? Does it work for other countries?

India suits this approach: many prices that move the CPI are set by public announcement. Examples are
cooperative milk prices, domestic LPG, petrol, and electricity tariffs set by state regulators. The government
publishes daily retail prices for food, and MoSPI moved to a new 2024-based series this year with published weights.
The method (carve out what you can observe, carry the rest on trend, combine index levels with official weights)
would carry over to other countries. But each one needs its own weights, sources, languages and price rules. We have
not tested any other country, so we don't claim it works there.

## 3. How do you know the backtest didn't see the future?

We can't prove it perfectly, and `docs/honest_limits.md` says so. What we do:
- Every search is limited to the target month by Tavily's date filters.
- The code checks the date in the page address or the page's published date and drops undated pages. An event counts
  only if its effective date is inside the month.
- A "leak guard" drops any page that states the official CPI figure for that month.
- The model's own memory cannot set the number, because Nemotron only extracts quoted lines and code does the
  arithmetic. [TBD: Nemotron training-data cutoff, from the model card.]
- All rules were frozen and committed before scoring (`docs/frozen_rules.md`, `docs/preregistration.md`), and
  scoring ran once (`results/score_lock.json`).

## 4. Did you tune on the test months?

No. Pass-through factors and rule changes were calibrated on 2025 only, and the rules were frozen before any test
month was scored (`docs/frozen_rules.md`). Amendment 1 was made before scoring and applies general scope rules
(domestic LPG only, retail only), not month-specific fixes. Everything changed after scoring is listed in
`docs/after_scoring_changes.md`, with dates and commits. None of it changes a scored number. One example: the 80%
range for the live months was widened because it held the official figure in only 5 of 9 replay months.

An independent event audit (`audit/event_audit.md`, PR bhavikjain026/shadow-cpi#4) found some events in the replay
data that are wrong or out of scope. A recall check (`audit/missed_events.md`) found changes that were missed. We
did **not** go back and fix those events, because that would mean tuning on the test months. We report them as they are.

## 5. What if the sealed October number is wrong?

Then we show it. The October prediction is sealed before 12 Nov with a SHA-256 fingerprint and a git tag, so it
can't be changed quietly afterwards. The Archive page shows the official figure, our miss, and whether it fell
inside the range. One month is a single data point: a miss inside the range is expected some of the time, and a miss
outside it would add to the evidence that the range is too narrow. We'd also publish the reasons for the miss, for
example a big change in a part of the basket we carry on trend.

## 6. How accurate is it vs the economists' poll?

[TBD: from replay. Mean absolute miss of (c) vs the Reuters poll on the months with a dated poll article, and over
all 9 months. Take the numbers from `results/scoreboard.md` and `results/baselines.csv`, and state the sample size.]
Whatever the numbers, say plainly that the poll is a strong baseline and the sample is small.

## 7. What exactly does Tavily do, and what does Nemotron do?

Tavily is how all web data enters the system (`docs/pipeline.md`):
- **Search** (news, date-limited to the month, English and Hindi) finds price quotes and announced price changes.
- **Extract** reads those pages, plus IBJA's gold and silver rate sheets, IOCL's domestic LPG price list and PPAC's
  petrol prices.
- **Map + Crawl** looks for circulars and tariff orders on official sites.

Two exceptions are logged direct downloads, not Tavily: MoSPI's official indices (a JSON API) and the
government's daily food prices (behind a CAPTCHA).

Nemotron on Nebius Token Factory only extracts:
- a small model decides whether a page states an Indian price;
- a mid model lists prices and price changes, each citing a numbered line;
- a large model writes the reporter brief from numbers code has already computed.

Code checks every cited line word for word and does all the maths.

## 8. What are the biggest limits?

From `docs/honest_limits.md`:
- Only 9 test months, so differences between methods could be luck. The 80% range is built from those same 9 misses.
- Only about 14–21% of the basket is measured each month; the rest is carried on trend.
- Replays search today's web with date filters, which can't perfectly recreate what was online at the time.
- Some items are composites: "gold" includes diamond and platinum jewellery, and "LPG" includes piped gas.
- The government food price data is collected by hand from behind a CAPTCHA.
- The event layer misses things. GST cuts can't be applied, and the recall check (`audit/missed_events.md`) found
  missed electricity changes and no bus fare search at all.
