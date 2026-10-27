# Shadow CPI v3: pre-registration

**Written 2026-10-26T18:58Z (UTC) = 27 Oct 2026, 00:28 IST. Committed before any v3 code existed.** No v3 prediction,
range or score had been computed when this file was committed; the commit that adds it is the timestamp of record.
Decided by the owner on 27 Oct 2026 (IST).

v3 is **experimental**. It is shown and sealed **beside** v1, never instead of it. v1 stays frozen: no v1 file, rule,
range, result, score lock or seal changes because of v3 (`docs/frozen_rules.md`, `docs/preregistration.md`).
v2 and its draft `v2/NOVEMBER_PREREG.md` are separate and are not changed by this file.

## 1. What v3 is: two numbers, one primary

| Name | Role | Rule |
|---|---|---|
| **v3a** | **primary**: the one quoted if v3 is mentioned at all | tier-weighted evidence (§2) |
| **v3b** | secondary | equal-weight average of trend, government prices and v1 (§3) |

Nothing in v3 is fitted. The tier weights (§2) and the equal weights (§3) are fixed here, before any v3 number exists.
Each method gets its own 80% range (§4).

## 2. v3a: tier-weighted evidence update

For every item v1 carves out, **item change = trend + w × (measured change − trend)**, where *trend* is v1's
`cpi_math.trend_change` and *measured change* is the change v1 itself uses for that item. *w* is fixed by the
evidence's tier:

| Tier | w | Which evidence |
|---|---|---|
| verified | **1.0** | official observed series: DoCA retail prices (the government price spine, × the 2025 pass-through factor, as v1), IOCL domestic LPG, PPAC Delhi petrol, IBJA gold and silver |
| corroborated | **0.7** | a news event with `confirmed_by_2_sources = true` in the month's manifest |
| single source | **0.4** | a news event with one source |

- "verified" here names the **tier** (an official series). It is not v1's per-event field `verified` (the cited line
  contains the number); every event v1 applies already has that field true.
- Because official series have w = 1.0, v3a equals v1 for them. v3a differs from v1 only where v1 applies a news
  event (electricity, rail, mobile, medicine, tuition, fuel before PPAC covers the month). For those items v1's
  change is trend + Σ applied change, so v3a's is **trend + Σ w(event) × applied change**, event by event.
- **Implementation (fixed now):** a copy of the month's inputs with each event's `applied_change` multiplied by its
  *w*, passed to v1's unchanged `shadow_cpi.predict.predict_month(month, "c", …)`. No v1 code is copied or edited.
  Test: with every *w* = 1.0 this reproduces v1's (c) exactly.

## 3. v3b: equal-weight model average

v3b = the **equal-weight (1/3 each) average of the predicted headline index LEVELS** of v1's models (a) trend only,
(b) spine only (the government price spine) and (c) v1, all from v1's unchanged `predict_month`; YoY is computed last
from that level (CLAUDE.md rule 4). Because the three share the same month-12 base, this equals the mean of their
three YoY predictions.

## 4. 80% range for each method: split conformal

- **Calibration set:** the method's own 9 absolute misses |prediction − published YoY| on **Jan–Sep 2026**
  (unrounded predictions; MoSPI's published YoY from `data/cpi_tidy.csv`), computed from saved inputs (0 credits).
- **Half-width q:** with n = 9 and α = 0.2, the ⌈(n + 1)(1 − α)⌉ = **8th smallest** of the 9 absolute misses.
- **Range:** prediction ± q. Symmetric. No floor, no skeptic widening (those belong to v1's Amendment 2).
- The same 9-month calibration set is used for **both** October and November. October is not added for November.
- **P(headline ≥ 6.0%)** for each method: a normal distribution with mean = the prediction and σ = q / 1.2816 (its
  central 80% is the range), the same construction as v1's Amendment 2. 6.0% is the threshold v1 uses.
- Labelled in the app and docs: **"calibrated on Jan–Sep 2026; tested on Oct and Nov"**.
- Assumption, stated: split conformal assumes October's and November's misses are exchangeable with Jan–Sep's. With
  n = 9 the guarantee is loose: at least 80% coverage on average over draws, not in every month.

## 5. Inputs: the same as v1's, checked

- **Jan–Sep 2026:** `shadow_cpi.predict.load_inputs()`, the inputs of v1's scored replay. Test: v3's own (c) equals
  `results/replay_predictions.json` for every month.
- **October and November 2026:** `build_nowcast.gather(month, cutoff, …)`, cache only (0 credits), after v1's real
  build. Before writing, the v3 builder checks against v1's `results/nowcast_<month>.json`: the same evidence cutoff,
  the same manifest SHA-256, the same code commit, and (c) recomputed by v3 equal to v1's `headline_yoy`. Any
  mismatch stops the build.

## 6. Sealing (29 Oct for October; with v1's November seal for November)

- v1 is sealed first, by the unchanged `seal_month.py` (`sealed/<month>.json`, `.sha256`, tag `seal-<month>`).
- Right after, in the same session: `sealed/<month>.v3.json` (both v3 numbers, ranges, probabilities, the input
  hashes) and `sealed/<month>.bundle.sha256` (SHA-256 of `<month>.json`, `<month>.sha256` and `<month>.v3.json`),
  committed and tagged **`seal-<month>-bundle`**. v1's file, hash and tag are not touched.
- Deadline: committed before **23:59 IST on the 29th of the month**, and before the official release. The tool
  refuses after that.
- A v3 seal is never redone.

## 7. Scoring (once each)

- **October:** after MoSPI's release on 12 Nov 2026. **November:** after the release (scheduled 12 Dec, likely
  Mon 14 Dec 2026).
- For v1, v3a and v3b side by side: miss and |miss| (pp), inside the 80% range or not, range width, and the **Brier
  score** of P(headline ≥ 6.0%), computed by the Brier function the drift-monitor branch adds. The same function is
  used for all three. If that branch scores a different event, each v3 method's probability for it comes from its
  §4 normal distribution.
- Two months cannot show which method is better. They are reported as two outcomes, not a verdict.
- **Jan–Sep 2026 v3 results may be shown only as "retrospective, not a test":** v3 was designed after v1's Jan–Sep
  scores were public, and §4 uses those months for its range.

## 8. How this differs from the first task card, and why

The card asked for (a) the tier-weighted update, (b) a model average of trend, government prices and v1 with weights
fitted on 2025, and (c) a split-conformal range from 2025 misses. Changed by the owner on 27 Oct, before any code:

1. **No fitted weights, and no 2025 calibration.** 2025 has index levels but no YoY in the 2024 series. v1's
   pass-through factors were fitted on Feb–Dec 2025, so v1 and the spine model are in-sample there. And v1 on 2025
   would apply no news events (the 2025 recall audit kept only raw milk extractions, which v1 never applies).
   Weights or ranges fitted on 2025 would be biased towards v1. Equal weights need no fitting.
2. **Two numbers instead of one.** (a) and (b) answer different questions, so each is its own method; v3a is primary.
3. **Ranges from Jan–Sep 2026.** This uses test months for the range only, as v1's Amendment 2 already does for the
   live months (CLAUDE.md rule 5 otherwise keeps test months out of tuning). No factor, weight, filter or rule is
   tuned on them, and v3's Jan–Sep results are never presented as a test (§7).

## 9. What will not happen

- No v1 file, rule, result, range or seal changes.
- The tier weights, the equal weights, the conformal rule and the scoring are not changed after any v3 number is seen.
- A v3 number is never presented as v1's, or the other way round.
