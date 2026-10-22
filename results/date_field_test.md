# Date field test (pilot)

Run 2026-10-22T12:26 UTC by `python -m v2.date_test`, pre-registered in `v2/DATE_TEST_PREREG.md`. 20 cases from the hand-built audit list (`audit/missed_events.md`), one frozen query each. A **pilot**: 20 cases cannot show small differences.

| Arm | What it does | Cases with a confirmed leak (Wilson 95%) | Leak fraction (bounds) | Valid evidence lost | Undated results | Credits | Median latency |
|---|---|---|---|---|---|---|---|
| A | no date fields | 9 of 20 (26%–66%) | 67% (20%–90%) | 34 of 40 | 8 | 20 | 3.80 s |
| B | start/end dates | 0 of 20 (0%–16%) | 0% (0%–47%) | 19 of 40 | 0 | 20 | 3.40 s |
| C | dates + filter_by_published_date | 0 of 20 (0%–16%) | 0% (0%–36%) | 12 of 40 | 0 | 20 | 3.55 s |
| D | C + our page-date check | 0 of 20 (0%–16%) | 0% (0%–31%) | 27 of 40 | 0 | 29 | 3.16 s |

C vs D (paired, exact McNemar): leaks only in C 0, only in D 0, p = 1.000. Undated results: B 0, C 0.

A **confirmed leak** needs independent version evidence: the Wayback Machine has no copy of the page on or before the cutoff, its first copy is after it, and Tavily's or the address's date is after the cutoff. The page date that arm D uses is never used to label a leak. Unconfirmed results set the bounds of the leak fraction.
