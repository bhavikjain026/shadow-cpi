# November 2026: conformal 80% range, experimental beside v1 (DRAFT)

> **DRAFT for the owner's review: not pre-registered yet.** It becomes a pre-registration only when the owner approves
> it and it is committed to main with a timestamp, before the November seal run. Nothing here changes v1, its range,
> the October seal or any score lock.

## Question
Does a split-conformal 80% range, computed from v2's own scored misses, cover the official November figure more
reliably than v1's leave-one-out range (which held the official figure in 5 of 9 replay months)?

## What is sealed
- **v1** (the headline call) and its range, exactly as sealed for October (`docs/frozen_rules.md`, Amendment 2): unchanged.
- **Beside it, labelled experimental:** v2's November prediction with a **conformal 80% range**. It is shown next to v1,
  never instead of it, and never changes v1's number or range.

## The conformal rule (fixed now)
1. **Calibration set:** the absolute misses |official − v2| of the scored months in `results/v2_score_lock.json`
   (`months[].miss`), plus October once MoSPI publishes it (12 Nov) and it is scored, if that happens before the
   November seal. No other month, no 2026 tuning of anything else.
2. **Quantile:** with n calibration misses and α = 0.2, the half-width q is the ⌈(n + 1)(1 − α)⌉-th smallest absolute
   miss (if that rank exceeds n, the range is reported as "unbounded at 80% with this n").
3. **Range:** v2's November prediction ± q. Symmetric; no floor, no skeptic widening (those belong to v1).
4. **Assumption, stated:** split conformal assumes the misses are exchangeable with November's miss. With n of about
   9–10 months the guarantee is loose (coverage at least 80% on average over draws, not in every month), and a
   regime change (e.g. October's RBI rate rise) can break exchangeability.

## Scoring (after the November release, scored once)
- Inside or outside, for v1's range and for the conformal range; both widths in pp.
- Reported together with the replay coverage of each rule computed leave-one-out on the calibration months (the
  conformal rule re-fitted without each month in turn), labelled "replay, not a test".
- One month cannot show which range is better; this is reported as a single outcome, not a verdict.

## Credits
None beyond the November seal run itself: the range is computed from saved misses (0 credits).

## Open points for the owner
- Include October in the calibration set if it is scored before the seal (recommended), or keep the 9 replay months only.
- Show the conformal range on Home, or only on the Replay page.
