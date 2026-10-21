# Changes made after scoring

The replay (Jan–Sep 2026) was scored once on 2026-10-21 (`results/score_lock.json`). Every change made after that
is listed here with its date, reason and commit. None of them changes a scored result.

- **2026-10-21 · commit `7b3f138`** · Record-only fix: announced_date in 7 test-month manifests (Feb, Apr–Sep; the
  June file already held an ISO date, so 6 files changed). No decision logic reads it; score_lock.json unchanged
  (c = 0.185 pp); March rebuild test passes (`tests/test_build_nowcast.py`, committed separately).
