# Date field test: pre-registration (a pilot)

**Written 2026-10-22T09:37:17Z (UTC), committed before any run.** Decided by the owner. Code: `v2/date_test.py`; tests:
`tests/test_v2_date_test.py`. Run once with `python -m v2.date_test`; the result file refuses a second run.

**Question.** Do Tavily's date fields keep pages published after an evidence cutoff out of the results, and what does
our own page-date check add?

## Cases
- **20 query-cutoff cases** sampled from `audit/missed_events.md` (transcribed in `v2/recall_reference.json`), a
  list built by hand search, independent of Tavily. Random seed **20261022** (`random.Random(20261022)`).
- **Deviation from "4 per month over 5 months", logged:** the reference has only three months with 4 or more changes
  (April 6, May 8, June 5; July and September have 3 each). So: 4 drawn from each of April, May and June, all 3 of July
  and of September, and 2 more drawn from the remaining April–June changes, all with the same seed.
- Cutoff = the v2 cutoff (`v2.rules.cutoff`: the 29th, or the month's last day). One **frozen English query** per
  case: the item's words + place + month (e.g. "milk price hike Tamil Nadu July 2026"). Two pairs of cases share a
  query (same item, state and month); they are kept as sampled. The cases are frozen in `v2/date_test_cases.json`:

| Case | Month | Cutoff | Query |
|---|---|---|---|
| E1 | 2026-04 | 2026-04-29 | electricity tariff hike Madhya Pradesh April 2026 |
| E2 | 2026-04 | 2026-04-29 | electricity tariff hike Maharashtra April 2026 |
| E4 | 2026-04 | 2026-04-29 | electricity tariff hike Jharkhand April 2026 |
| M2 | 2026-04 | 2026-04-29 | milk price hike Madhya Pradesh April 2026 |
| F3 | 2026-05 | 2026-05-29 | petrol diesel price hike India May 2026 |
| M3 | 2026-05 | 2026-05-29 | milk price hike India May 2026 |
| M4 | 2026-05 | 2026-05-29 | milk price hike Madhya Pradesh May 2026 |
| M5 | 2026-05 | 2026-05-29 | milk price hike Maharashtra May 2026 |
| M6 | 2026-05 | 2026-05-29 | milk price hike Bihar, Jharkhand May 2026 |
| E5 | 2026-06 | 2026-06-29 | electricity tariff hike Uttar Pradesh June 2026 |
| E6 | 2026-06 | 2026-06-29 | electricity tariff hike Delhi June 2026 |
| L2 | 2026-06 | 2026-06-29 | LPG cylinder price hike India June 2026 |
| M7 | 2026-06 | 2026-06-29 | milk price hike Kerala June 2026 |
| T3 | 2026-06 | 2026-06-29 | bus fare hike Odisha June 2026 |
| E7 | 2026-07 | 2026-07-29 | electricity tariff hike Chhattisgarh July 2026 |
| M8 | 2026-07 | 2026-07-29 | milk price hike Tamil Nadu July 2026 |
| M9 | 2026-07 | 2026-07-29 | milk price hike Tamil Nadu July 2026 |
| E8 | 2026-09 | 2026-09-29 | electricity tariff hike Jammu and Kashmir September 2026 |
| M11 | 2026-09 | 2026-09-29 | milk price hike Tamil Nadu September 2026 |
| M12 | 2026-09 | 2026-09-29 | milk price hike Tamil Nadu September 2026 |

## Arms (run close together, in a seeded random order per case; everything else identical)
Common: `topic` news, `search_depth` basic, `max_results` 3, `include_published_date` true, the same query,
the same domains (`include_domains` = the English news list in `shadow_cpi/evidence.py`, mode prefer), no language.
- **A:** no date parameters, `filter_by_published_date` false.
- **B:** `start_date` = the month's first day, `end_date` = the cutoff, `filter_by_published_date` false.
- **C:** the same window, `filter_by_published_date` true.
- **D:** C's results plus our page-date check: Tavily Extract of each result; only an **explicit** published or
  updated date on the page counts (the later if both); missing or ambiguous (two different dates for the same word)
  = **unknown, never safe**, so D keeps only results whose page date is known and on or before the cutoff. D makes no
  extra search.

## Labels (per result; never from the page date D uses)
- **Confirmed leak (L):** independent version evidence only: the Wayback Machine CDX API (a logged direct download,
  the same exception as MoSPI) lists **no capture on or before the cutoff**, its first capture is after the cutoff,
  **and** Tavily's published date or the date in the address is after the cutoff.
- **Confirmed pre-cutoff (P):** a Wayback capture on or before the cutoff.
- **Post-cutoff date flag (F):** any date signal after the cutoff without that evidence; **unknown (U)** otherwise.

## Metrics (per arm)
1. Confirmed-leak incidence per case: cases with at least one confirmed leak among the arm's kept results, x of 20,
   **Wilson 95%** interval.
2. Leak fraction L/(L+P), with **bounds** for the unconfirmed results (F and U): lower = L/(all), upper =
   (L + unconfirmed)/(all).
3. Valid evidence lost: valid = a P result whose title or snippet names the item; lost = valid results found by any
   arm and not kept by this arm.
4. **C vs D paired:** cases with a confirmed leak in C but not D, and in D but not C; **exact McNemar** (two-sided).
5. Undated results (no Tavily published date), B vs C.
6. Search + Extract credits and median latency (Tavily's `response_time`) per arm. Each unique address is
   extracted **once** for evaluation (C's first, which are D's check; D is costed as C's searches plus those
   extracts).

## Output and cap
`results/date_field_test.json` and `results/date_field_test.md`: a one-page plain-English summary with the
numbers, called a **pilot**. Credit cap **150** (`date-test` in `config/budget.json`); a cap stops it cleanly and
marks it incomplete. Not run until the Amendment E/F arms have finished.

**Bug fix, 2026-10-22 (logged, before any result was seen).** The first run stopped with an error after its searches, extracts and Wayback lookups, before writing any result: when the text after "published"/"updated" looked like a date but could not be read (e.g. a month name we do not parse), the page-date reader kept an empty entry and then crashed. Fix: such a date now leaves that word with no date (unknown), as the rule says. Re-run from the cache: 0 extra credits, same calls.
