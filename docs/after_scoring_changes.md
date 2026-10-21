# Changes made after scoring

The replay (Jan–Sep 2026) was scored once on 2026-10-21 (`results/score_lock.json`). Every change made after that
is listed here with its date, reason and commit. None of them changes a scored result.

- **2026-10-21 · commit `7b3f138`** · Record-only fix: announced_date in 7 test-month manifests (Feb, Apr–Sep; the
  June file already held an ISO date, so 6 files changed). No decision logic reads it; score_lock.json unchanged
  (c = 0.185 pp); March rebuild test passes (`tests/test_build_nowcast.py`, committed separately).

## 1. Amendment 2: wider 80% range and P(headline ≥ 6.0%), live months only

- **Date:** 2026-10-21
- **Decided by:** the owner
- **Reason:** the pre-registered leave-one-out 80% range held the official figure in only 5 of 9 scored months,
  so it is too narrow to seal. The scored months keep their original ranges and the 5-of-9 figure.
- **Change:** for 2026-10 and 2026-11 only, the 80% range is the prediction ± the 80th percentile of |miss| of (c)
  over the 9 scored months, never narrower than the pre-registered range. P(headline ≥ 6.0%) is added from the same
  range (normal, central 80% = the range). 6.0% is the RBI's Q3 projection. Full text: `docs/frozen_rules.md`,
  Amendment 2. Code: `shadow_cpi/live_range.py`; tests: `tests/test_build_nowcast.py`.
- **Effect on October (dry run, 2026-10-21):** width 0.568 pp (± 0.284) instead of 0.470 pp. The new range is
  centred on the prediction; the pre-registered one sat above it, because (c) under-predicted in 7 of 9 months.
- **Commit:** `afc2241`

## 2. October builder (`build_nowcast.py`) and a reusable observed-series step

- **Date:** 2026-10-21
- **Reason:** the seal needs `results/nowcast_<month>.json` from the same code that was scored.
- **Change:** `build_nowcast.py <month> --cutoff <date>` calls `shadow_cpi.predict.predict_month(month, "c", ...)`
  (the scored function, not a copy). The gold/silver/LPG/petrol step of `run_replay_layers.py` was moved, unchanged,
  into `observed_layers()` and `cached_lpg_petrol()` so the builder and the replay share it.
- **Check:** rebuilt from cache, all 9 scored months reproduce their scored (c) number exactly (bit for bit);
  March is a permanent test (`test_builder_reproduces_scored_march_exactly`).
- **Needs the owner's OK — IOCL gap and the cutoff:** Amendment 1 (a) records an LPG gap when IOCL's list was saved
  before the month's data. The replay compared with the month end. For a live month, the builder compares with the
  evidence cutoff instead (min(month end, cutoff)), because a list saved on 29 Oct can never be dated after 31 Oct
  before the seal. For the 9 scored months this gives the same answer (checked). If the owner prefers the month-end
  reading, October LPG is always a gap and follows trend.
- **Commit:** `afc2241`
