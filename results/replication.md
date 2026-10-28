# Date test replication

Run 2026-10-28T13:56 UTC by `python -m v2.replication`, pre-registered in `v2/REPLICATION_PREREG.md`. Arms: **A** no dates; **C** start/end dates (the 30 days to the cutoff) + `filter_by_published_date`. Cutoff = the day before each event. First Wayback pass = primary result.

## Headline (first pass)

- **date-test rule (v2/DATE_TEST_PREREG.md):** arm A leaked in 14 of 22 cases; arm C leaked in **0 of 22** cases; exact McNemar p = 0.0001.
- **finance rule (v2/FINANCE_PREREG.md):** no eligible cases; nothing to report.

## date-test rule (v2/DATE_TEST_PREREG.md): 22 cases

| Arm | Cases with a confirmed leak (Wilson 95%) | Leak results | Date-flag cases | Valid evidence lost | Undated | Wayback failed | Credits | Median latency |
|---|---|---|---|---|---|---|---|---|
| A | 14 of 22 (43%–80%) | 29 of 66 | 11 | 17 of 22 | 10 | 16 | 22 | 3.56 s |
| C | 0 of 22 (0%–15%) | 0 of 55 | 0 | 4 of 22 | 0 | 17 | 22 | 3.67 s |

A vs C, exact McNemar (paired by case): leaks only in A 14, only in C 0, p = 0.0001.

Sensitivity (pre-registered): the 9 hand-built reference cases alone: A 7 of 9 (45%–94%); C 0 of 9 (0%–30%); exact McNemar p = 0.0156.

## Wayback retry of failed lookups (secondary; the first pass above stays primary)

30 lookups failed in the first pass and were retried (only lookups that failed; 3 tries, 5 s apart; same CDX query and labels); 30 recovered, 0 still failed.

- date-test rule (v2/DATE_TEST_PREREG.md): A 19 of 22, C 0 of 22; McNemar p = 3.8e-06; valid evidence lost A 29 of 36, C 5 of 36.

## Pilot + replication pooled (secondary; per rule, never added across rules; first passes)

- date-test rule (v2/DATE_TEST_PREREG.md): 20 pilot + 22 replication cases. A 23 of 42 (40%–69%); C 0 of 42 (0%–8%); exact McNemar p = 2.4e-07.
- finance rule (v2/FINANCE_PREREG.md): 14 pilot + 0 replication cases. A 2 of 14 (4%–40%); C 0 of 14 (0%–22%); exact McNemar p = 0.5000.
