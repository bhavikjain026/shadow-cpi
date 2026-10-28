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

## Addendum: cache-served arm-A responses (logged 2026-10-28, after the results; descriptive, offline, 0 credits; nothing above changes)

Every outside call goes through the Recorder cache. 4 of the 44 searches were served from it, all in arm A (no dates: the same query and parameters as an earlier call). Arm C's searches were all fresh.

- **VE05 arm A** reused the response of RR-L1 arm A (request 9a47ee67-e33d-455f-aaf7-bbe77eca42a4); same run; confirmed leak in this case: yes.
- **RR-F1 arm A** reused the response of date test F3 arm A (request 100cdaa0-7de1-46d5-b1e8-db0fe10fb1e2); that is the pilot's search of 22 Oct; confirmed leak in this case: yes.
- **RR-F2 arm A** reused the response of date test F3 arm A (request 100cdaa0-7de1-46d5-b1e8-db0fe10fb1e2); that is the pilot's search of 22 Oct; confirmed leak in this case: yes.
- **RR-F4 arm A** reused the response of date test F3 arm A (request 100cdaa0-7de1-46d5-b1e8-db0fe10fb1e2); that is the pilot's search of 22 Oct; confirmed leak in this case: yes.

**Not pre-registered, descriptive.** Without the 3 cases that reused the pilot's response (RR-F1, RR-F2, RR-F4): A 11 of 19 (36%–77%), C 0 of 19 (0%–17%); exact McNemar p = 0.0010. Without all 4 cache-served cases: A 10 of 18 (34%–75%), C 0 of 18 (0%–18%); exact McNemar p = 0.0020.

**Pooled count:** the pooled arm-A count above (23 of 42) includes the reused pilot response: date test F3 arm A is one of the pilot's confirmed-leak cases, and the same response counts again in 3 replication cases (RR-F1, RR-F2, RR-F4), with each case's own cutoff.
