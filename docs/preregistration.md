# Pre-registration: Prompt 3 replay (Jan–Sep 2026)

Written and committed on 2026-10-21, **before any test-month prediction was computed or compared with an official
figure**. The rules in `docs/frozen_rules.md` (including Amendment 1) are the inputs. Scoring runs **once**
(`tools/score_replay.py`, which writes `results/score_lock.json` and refuses a second run). Any later change is a
**bug fix only**: it must be logged at the end of this file with its date, reason and commit, and both the old and
new scores must be kept.

## What is predicted
For each test month *m* (2026-01 … 2026-09): MoSPI's published all-India Combined CPI year-on-year inflation (%)
(`published_yoy` of CPI (General) in `data/cpi_tidy.csv`, 2024 series).

**Information used for month *m*:**
- official indices up to *m−1*;
- evidence for *m* only: spine prices for *m* and *m−1*; IBJA, IOCL and PPAC prices; events effective in *m*.

All of it was retrieved in October 2026 with date filters. This is a replay limitation, stated in `honest_limits.md`.

## Models (all aggregate predicted index LEVELS with official 2024-series weights; YoY is computed last)
**Components:** the 43 groups. A tracked item is carved out of its group, and the rest of the group (its residual)
follows the group's trend (`cpi_math.build_components`).

**Trend** for any component = `cpi_math.trend_change` (last 3 months' average month-on-month change + 0.5 × the
seasonal deviation, 2025 base), using data up to *m−1* only.

**Headline:**
- predicted headline level = published headline(*m−1*) × aggregate(predicted levels) ÷ aggregate(*m−1* levels);
- YoY = predicted level ÷ published headline(*m−12*) − 1, in %.

| Model | Carved-out items and their change |
|---|---|
| **(a) Trend only** | Nothing carved out; every group follows its trend (= baseline B2). |
| **(b) Spine only** | The spine foods with `use_spine = true` (onion, tomato, potato, tur dal, edible oils = sub-class 01.1.5.1, atta, milk, eggs): change = 2025 factor × the spine's change (geometric mean over zones). No spine pair → trend. |
| **(c) Spine + Tavily evidence** | (b), plus: **gold and silver** = factor × IBJA change (≥ 5 trading days in both months, else trend); **LPG** = factor × IOCL change (an IOCL gap → trend); **petrol** = 1.0 × PPAC change when PPAC has prices in both months, else trend + the fuel events' applied change; **items without an observed series** (electricity, rail fare, mobile, medicine, tuition fees) = trend + the sum of their events' applied change (change × share of month × state weight). Milk events are not applied, because milk is observed through the spine. GST events are never applied. |
| **(c-strict)** | (b) plus the official observed series only (IBJA, IOCL, PPAC). News events are left out. This is the strict tier, reported separately from (c), which adds the exploratory tier. |

**Coverage** = share of the official basket weight whose change comes from evidence (observed or event) rather than
trend (`cpi_math.coverage`).

## Metric (decided now)
- **Miss** = predicted YoY − published YoY, in percentage points.
- **Primary metric:** mean absolute miss over all 9 test months.
- **Secondary metric:** direction hit-rate. A hit means sign(predicted − last month's published YoY) =
  sign(actual − last month's published YoY). If the actual is unchanged (|actual − last| < 0.005), a hit means
  |predicted − last| < 0.05.
- **Compared with:** B1 (last month's YoY) and B2 = (a), from `results/baselines.csv`. Also compared with the
  economists' poll on its 6 dated months only. The poll is reported but is not part of the GO rule.

## GO rule (decided now)
**GO** if and only if mean |miss| of **(c)** < mean |miss| of **B1** AND mean |miss| of **(c)** < mean |miss| of
**(a) trend only**. Otherwise **NO-GO**.

Reported honestly whatever the result: (c) vs (b) (accuracy change and coverage gain), (c) vs (c-strict), and the
poll comparison.

## Range method (decided now)
- **80% empirical interval from replay misses of (c).**
- **For a test month *m* (leave-one-out):** take the misses of (c) in the other 8 test months. Their 10th and 90th
  percentiles (linear interpolation) are q10 and q90. Range = [prediction − q90, prediction − q10]. "Inside the
  range in N of 9 months" uses these out-of-sample ranges.
- **For the October seal:** the same, using all 9 test-month misses.

**Skeptic ("Try to prove this wrong"):** for each month, the 3 components with the largest absolute contribution to
predicted inflation get one counter-search each:
- Tavily news search, basic, the month's window, snippets only (no extract), hard cap `skeptic` (48 credits).
- The query asks for the opposite direction to the prediction: "<name> price fall cheaper" if the contribution is
  positive, "<name> price hike rise" if negative.
- Nemotron reads the snippets and cites lines; code keeps a quote only if its number is in the cited line, it names
  the item, and it contains an opposite-direction word.
- **2 or more verified contrary quotes** → that month's range is widened by 50% on each side of the prediction.

## What will not happen
- No factor, filter, rule, window or parameter is changed after seeing a score.
- The test months are not re-searched; everything comes from the cache, except the skeptic searches above.

## Bug-fix log
(empty at registration)

- **2026-10-21 · Amendment 3** (after scoring): four general bug fixes found by an independent audit (retail-only
  context, premium fuel grades, national scope, one event per kind × state × month). Re-scored once from cache.
  (c) mean absolute miss **0.185 → 0.194 pp**; (a) 0.212, (b) 0.225, B1 0.468 unchanged; GO still met; 5 of 9
  inside the range before and after. Old and new scores: `docs/after_scoring_changes.md` §4,
  `results/*_before_bugfix_2026-10-21T151419.*`, `results/score_lock.json` (`history`). Commit `b88a6fd`.
