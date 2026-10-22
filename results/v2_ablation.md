# Search-parameter ablation (Amendment E)

**DEVELOPMENT data**, Jan–Sep 2026, computed 2026-10-22T11:26 UTC by `python -m v2.ablation --metrics` from `v2/ablation/`. Pre-registered in `v2/PREREGISTRATION.md` (Amendment E); matcher unchanged since db2984c; 29 known changes.

| Arm | Searches written by | Recall | False events (upper bound) | Credits per verified event | Median Tavily latency | Credits (new now) | Incomplete months |
|---|---|---|---|---|---|---|---|
| A | code (fixed templates) (en, hi, mr, ta, te, kn, bn) | 6 of 29 | 6 of 8 | 12.8 | 3.12 s | 205 (0) | none |
| B | Nemotron (en, hi) | 2 of 29 | 2 of 3 | 13.0 | 3.12 s | 117 (117) | none |
| C | Nemotron (en, hi, mr, ta, te, kn, bn) | 2 of 29 | 1 of 1 | 23.0 | 3.15 s | 184 (169) | none |
| T | Tavily auto_parameters (B's query texts) (en, hi) | 0 of 29 | 0 of 0 | — | 6.30 s | 121 (121) | none |

**Verdict (Amendment F, margin ±1 known change):** about equal on recall: A; ranked within that group by credits per verified event, then false events: A. Lower recall: B, C, T.

**Diagnostics (reported only, addendum to Amendment E; no target):**

| Arm | Duplicate results | Duplicate verified claims | Params corrected by code | Searches dropped by code | Plan retries (Super) | Super re-reads | Plan abstentions | Reader abstentions (of pages read) |
|---|---|---|---|---|---|---|---|---|
| A | 2 | 11 | 0 | 0 | 0 | 282 | 0 | 173 of 674 |
| B | 15 | 1 | 0 | 0 | 0 | 180 | 0 | 33 of 281 |
| C | 31 | 3 | 0 | 0 | 6 | 267 | 1 | 200 of 582 |
| T | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 of 0 |

False events: distinct CPI-moving verified events that match none of the 29 known changes; the reference list is the audit's, so this is an upper bound. Credits are Tavily's own per-call counts, including calls served from the cache (arm A is costed as when first run).
