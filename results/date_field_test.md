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

## Addendum (offline, added after the results; descriptive, nothing above changes)

- **Confirmed-leak rate per arm, Wilson 95%:** A 9 of 20 (26%–66%); B 0 of 20 (0%–16%); C 0 of 20 (0%–16%); D 0 of 20 (0%–16%).
- **A vs B, exact McNemar (paired by case):** leaks only in A 9, only in B 0, p = 0.0039.
- **C vs D, exact McNemar (paired by case):** leaks only in C 0, only in D 0, p = 1.0000.
- **Date flags** (a post-cutoff date from Tavily, the address or the page, without Wayback confirmation; not confirmed leaks): A 20 results in 13 cases; B 0 results in 0 cases; C 0 results in 0 cases; D 0 results in 0 cases.
- **What D flagged that C didn't:** D's page-date check removed 33 of C's 59 results: no readable page date 33. Of those, 20 were Wayback-confirmed from before the cutoff (valid evidence lost), 0 confirmed leaks and 13 unconfirmed; D flagged 0 results for a page date after the cutoff that C had kept.
- **T+dates (exploratory, `v2/ablation/arm_Td_*.json`):** with our start/end dates sent, auto_parameters still reported time_range w 47, d 8, y 1 over 56 searches, yet 532 of 532 dated results fell inside the supplied window.
