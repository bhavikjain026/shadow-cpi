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

## Network retry of failed Wayback lookups (logged; the first pass above stays primary)

2026-10-25T13:06 UTC, `tools/wayback_retry.py date`: the 11 lookups that failed in the first pass were retried (only lookups that failed; 3 tries, 5 s apart; same CDX query and labels); 11 recovered, 0 still failed. First pass and after retry, side by side:

| Arm | Confirmed-leak cases (Wilson 95%): first pass | after retry | Leak fraction (bounds): first pass | after retry | Valid evidence lost: first pass | after retry |
|---|---|---|---|---|---|---|
| A | 9 of 20 (26%–66%) | 10 of 20 (30%–70%) | 67% (20%–90%) | 61% (23%–85%) | 34 of 40 | 39 of 48 |
| B | 0 of 20 (0%–16%) | 0 of 20 (0%–16%) | 0% (0%–47%) | 0% (0%–36%) | 19 of 40 | 22 of 48 |
| C | 0 of 20 (0%–16%) | 0 of 20 (0%–16%) | 0% (0%–36%) | 0% (0%–36%) | 12 of 40 | 20 of 48 |
| D | 0 of 20 (0%–16%) | 0 of 20 (0%–16%) | 0% (0%–31%) | 0% (0%–31%) | 27 of 40 | 35 of 48 |

Exact McNemar, first pass → after retry: A vs B p = 0.0039 → 0.0020; C vs D p = 1.0000 → 1.0000. The retry recovers lookups only; the labelling rules and the pre-registered first-pass numbers are unchanged.
