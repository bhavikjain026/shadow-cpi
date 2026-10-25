# Finance look-ahead check

Run 2026-10-25T12:57 UTC by `python -m v2.finance_lookahead`, pre-registered in `v2/FINANCE_PREREG.md` (with Amendment 1). **Exploratory**: it changes no scored verdict. Outcomes judged from search titles and snippets only. Arms: **N** no dates; **D** start/end dates (the 30 days to the cutoff) + `filter_by_published_date`. Cutoff = the day before each event.

## All 14 events

| Arm | Confirmed-leak events (Wilson 95%) | Snippet-leak events (Wilson 95%) | Date-flag events | Confirmed / snippet / date-flag results | Valid evidence lost | Undated | Credits | Median latency |
|---|---|---|---|---|---|---|---|---|
| N | 2 of 14 (4%–40%) | 14 of 14 (78%–100%) | 9 | 6 / 44 / 12 of 70 | 10 of 11 | 2 | 14 | 3.17 s |
| D | 0 of 14 (0%–22%) | 0 of 14 (0%–22%) | 0 | 0 / 0 / 0 of 67 | 1 of 11 | 0 | 14 | 1.44 s |

N vs D, exact McNemar on confirmed-leak events (pre-registered (metric 3)): only in N 2, only in D 0, p = 0.5000.

N vs D, exact McNemar on snippet-leak events (descriptive): only in N 14, only in D 0, p = 0.0001.

## 13 events, without C4 (date from the board-meeting notice; no official outcome filing found)

| Arm | Confirmed-leak events (Wilson 95%) | Snippet-leak events (Wilson 95%) | Date-flag events | Confirmed / snippet / date-flag results | Valid evidence lost | Undated | Credits | Median latency |
|---|---|---|---|---|---|---|---|---|
| N | 2 of 13 (4%–42%) | 13 of 13 (77%–100%) | 8 | 6 / 41 / 10 of 65 | 10 of 11 | 2 | 13 | 3.11 s |
| D | 0 of 13 (0%–23%) | 0 of 13 (0%–23%) | 0 | 0 / 0 / 0 of 62 | 1 of 11 | 0 | 13 | 1.44 s |

N vs D, exact McNemar on confirmed-leak events (pre-registered (metric 3)): only in N 2, only in D 0, p = 0.5000.

N vs D, exact McNemar on snippet-leak events (descriptive): only in N 13, only in D 0, p = 0.0002.

**Confirmed leak** = states the outcome, and the Wayback Machine has no copy on or before the cutoff, its first copy is after it, and Tavily's or the address's date is after it. **Snippet leak** = states the outcome with a post-cutoff date, not Wayback-confirmed (reported separately, never counted as confirmed). **Date flag** = a post-cutoff date on a result that does not state the outcome. With 13–14 events the intervals are wide.
