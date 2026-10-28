# Post-hoc statistics (post-hoc, not pre-registered)

Built by `python tools/build_posthoc_stats.py` from committed per-case labels; 0 credits. Nothing here was pre-registered and nothing here changes a verdict.

## Exact McNemar, no dates vs dates + filter (pre-registered initial pass, paired by case)

| Study | Rule | Cases | Leaks, no dates | Leaks, dates + filter | Only no dates | Only dates + filter | Exact p (two-sided) |
|---|---|---|---|---|---|---|---|
| date test | date-test rule (v2/DATE_TEST_PREREG.md) | 20 | 9 | 0 | 9 | 0 | 0.0039 |
| replication | date-test rule (v2/DATE_TEST_PREREG.md) | 22 | 14 | 0 | 14 | 0 | 0.00012 |
| finance | finance rule (v2/FINANCE_PREREG.md, as amended) | 14 | 2 | 0 | 2 | 0 | 0.5 |
| pooled | date-test rule; pilot + replication | 42 | 23 | 0 | 23 | 0 | 2.4e-07 |

## The pooled zero

0 detected of 42 with dates + filter (Wilson 95% 0%–8%). Rule of three: the true leak rate is below 7.1% with about 95% confidence (exact one-sided bound 6.9%).

## Replication without the cache-served responses (reused from the logged addendum)

4 no-dates answers were served from our cache, 3 of them the pilot's own response. Without those 3 cases: no dates 11 of 19, dates + filter 0 detected of 19 (descriptive, not pre-registered (results/replication.md addendum)).
