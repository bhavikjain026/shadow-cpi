# Leak check E: exact_match back-dating (exploratory)

Run 2026-10-26T11:53 UTC by `python -m v2.leakcheck E`, pre-registered in `v2/LEAKCHECK_PREREG.md`. Descriptive only. 40 seeded verified quotes from the chain-of-custody list; one verbatim span each, searched with `exact_match` twice: dated (end_date = cutoff + filter_by_published_date) and undated.

| Outcome | Quotes | Share (Wilson 95%) |
|---|---|---|
| found before cutoff | 25 of 40 | 62% (47%–76%) |
| found only without dates | 8 of 40 | 20% (10%–35%) |
| not found either way | 7 of 40 | 18% (9%–32%) |

Found before the cutoff by the source page 23, by another page only 2. The undated search returned the source page for 25 quotes. `exact_match` can return nothing for text that is online; that is reported as is.

Credits: 80 (2.0 per quote). Every call's request_id and response SHA-256 are in `results/leakcheck_exact_match.json`.
