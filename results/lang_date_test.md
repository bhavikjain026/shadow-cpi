# Language date test (pilot)

Run 2026-10-26T19:02 UTC by `python -m v2.lang_date_test`, pre-registered in `v2/LANG_DATE_PREREG.md`. 12 cases from the hand-built audit list (Hindi 4, Marathi 4, Tamil 4), one frozen query each in its language, with Tavily's `language` field set. A **pilot**: 12 cases cannot show small differences. Compared with the English date test (`results/date_field_test.md`, first pass).

| Arm | What it does | Cases with a confirmed leak (Wilson 95%) | Leak fraction (bounds) | Valid evidence lost | Undated share | Dated outside the window | Credits | Median latency |
|---|---|---|---|---|---|---|---|---|
| A | no date fields | 3 of 12 (9%–53%) | 40% (11%–83%) | 8 of 13 | 17 of 36 (47%) | 15 | 12 | 4.36 s |
| C | dates + filter_by_published_date | 0 of 12 (0%–24%) | 0% (0%–57%) | 5 of 13 | 0 of 30 (0%) | 0 | 12 | 4.71 s |
| D | C + our page-date check | 0 of 12 (0%–24%) | 0% (0%–33%) | 12 of 13 | 0 of 3 (0%) | 0 | 16 | 4.13 s |

## By language, next to English

| Language | Cases | A: leak cases | C: leak cases | D: leak cases | A undated | C undated | C dated outside window | C valid lost | D results with no readable page date |
|---|---|---|---|---|---|---|---|---|---|
| Hindi | 4 | 3 | 0 | 0 | 0 of 12 | 0 of 6 (0%) | 0 | 0 of 5 | 5 of 6 |
| Marathi | 4 | 0 | 0 | 0 | 11 of 12 | 0 of 12 (0%) | 0 | 5 of 8 | 10 of 12 |
| Tamil | 4 | 0 | 0 | 0 | 6 of 12 | 0 of 12 (0%) | 0 | 0 of 0 | 12 of 12 |
| English (date test) | 20 | 9 | 0 | 0 | 8 of 60 | 0 of 59 (0%) | 0 | 5 of 33 | 33 of 59 |

Paired with English on the 6 cases in both tests (M2, E7, E2, M8, M9, M11), exact McNemar on confirmed-leak cases: A English only 4, language only 1, p = 0.375; C English only 0, language only 0, p = 1.000; D English only 0, language only 0, p = 1.000.
C vs D (paired, exact McNemar): leaks only in C 0, only in D 0, p = 1.000.

**Date fields by language:** no pre-registered difference from English (arm C kept nothing dated outside the window, its undated share was within 20 points of English, and it had no confirmed leak).

A **confirmed leak** needs the Wayback Machine: no copy of the page on or before the cutoff, its first copy after it, and Tavily's or the address's date after the cutoff. D's page date never labels a leak. D's page-date reader is the English test's, unchanged: it reads English and Hindi date words only, so "no readable page date" in Marathi and Tamil measures our reader as much as the page.

## Addendum (offline, added after the results; post-hoc, nothing above changes)

Not pre-registered: noticed when reading arm C's Tamil results (sports and car pages). Results whose title or snippet names the item, and results from the language's preferred news domains, arms A and C:

| Language | A: names the item | C: names the item | A: preferred domain | C: preferred domain |
|---|---|---|---|---|
| Hindi | 12 of 12 | 6 of 6 | 3 of 12 | 3 of 6 |
| Marathi | 10 of 12 | 4 of 12 | 6 of 12 | 0 of 12 |
| Tamil | 4 of 12 | 0 of 12 | 0 of 12 | 0 of 12 |
| English | 55 of 60 | 41 of 59 | 13 of 60 | 20 of 59 |

With the date window and `filter_by_published_date` set, the date fields did their job in every language (nothing dated outside the window, no undated result, no confirmed leak), but relevance fell further in Marathi and Tamil than in English or Hindi. Twelve cases, post-hoc: a lead to check, not a finding.
