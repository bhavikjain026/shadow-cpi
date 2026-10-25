# Search-parameter ablation (Amendments E and F)

**DEVELOPMENT data**, Jan–Sep 2026. Metrics computed once, 2026-10-22T11:26 UTC (commit 5b1eec0); this page re-presents them with corrected labels (see the label fix below). Matcher unchanged since db2984c; 29 known changes.

## Reconciliation (every number below comes from this table)

| Arm | Credits spent | Search calls | Verified claims | Distinct verified events | Events matched to the 29 | Not matched (may include real changes outside the list; see the check below) | Recall (of the 29) |
|---|---|---|---|---|---|---|---|
| A | 205 | 117 | 27 | 16 | 6 | 10 | 6 of 29 |
| B | 117 | 72 | 10 | 9 | 2 | 7 | 2 of 29 |
| C | 184 | 117 | 11 | 8 | 2 | 6 | 2 of 29 |
| T | 121 | 72 | 0 | 0 | 0 | 0 | 0 of 29 |

- **Distinct verified event:** a distinct (item, effective date, set of states) among an arm's verified claims. **Recall** counts the 29 known changes found by any verified claim; one event can match one change and several pages can report it, so recall and matched events differ.
- **False events (upper bound)** = verified events of an item that moves CPI by itself (electricity, diesel, bus, rail, mobile) that match none of the 29, out of all such events (pre-registered, Amendment E metric 2). Milk, LPG and petrol events are left out because their spine or official series moves the number.
- **Credits per verified event** = credits spent ÷ distinct verified events of any item (Amendment E metric 3).

## Result

| Arm | Searches written by | Recall | False events (upper bound): unmatched of CPI-moving events | Credits per verified event | Credits per known change found (added after scoring; descriptive) | Median Tavily latency (descriptive; pre-registered with no target, not used in the verdict) | Real new credits (charged in this test) | Incomplete months |
|---|---|---|---|---|---|---|---|---|
| A | code (fixed templates) (en, hi, mr, ta, te, kn, bn) | 6 of 29 | 6 of 8 | 12.8 (205 ÷ 16) | 34.2 (205 ÷ 6) | 3.12 s | 0 | none |
| B | Nemotron (en, hi) | 2 of 29 | 2 of 3 | 13.0 (117 ÷ 9) | 58.5 (117 ÷ 2) | 3.12 s | 117 | none |
| C | Nemotron (en, hi, mr, ta, te, kn, bn) | 2 of 29 | 1 of 1 | 23.0 (184 ÷ 8) | 92.0 (184 ÷ 2) | 3.15 s | 169 | none |
| T | Tavily auto_parameters (B's query texts) (en, hi) | 0 of 29 | 0 of 0 | — (121 ÷ 0) | — (121 ÷ 0) | 6.30 s | 56 | none |

**Verdict (Amendment F, margin ±1 known change), unchanged:** top group A; ranking A; lower recall B, C, T.

Arm A's credits are those of its calls when first made, in the issue 4 and issue 14 runs: the flight recorder has 213 uncached Tavily calls tagged `v2:events`, 205 credits, equal to the credit ledger's `v2-issue4` (150) + `v2-issue14` (55). Arm A itself re-ran them from the cache at 0 new credits.

**Two credit counts.** The credit columns count every call at its original cost (as agreed for this table). *Real new credits* is what the test itself charged; for arm T it was corrected 121 → 56 (logged): 41 of its 72 searches were cache hits that a budget bug charged again (fixed in 070fa6e; ledger offset row `phantom-T-2026-10-22`).

**Provenance (Amendment F):** request IDs + response hashes on every call of arms C and T (262 of 262); A and B ran before this logging existed (their responses are still in the recorder's cache).

**Label fix (logged; no number changed).** Before: "False events (upper bound) | 6 of 8" next to "Recall 6 of 29" for arm A, which read as 6 false of 8 found. After: the column says it counts unmatched events among CPI-moving items only (8 for arm A, 2 of them matched: E1 and E4), and the reconciliation table shows all events. The formula is the pre-registered one; the code was right.

## Diagnostics (reported only; addendum to Amendment E)

| Arm | Duplicate results | Duplicate verified claims | Params corrected by code | Searches dropped by code | Plan retries (Super) | Super re-reads | Plan abstentions | Reader abstentions (of pages read) |
|---|---|---|---|---|---|---|---|---|
| A | 2 | 11 | 0 | 0 | 0 | 282 | 0 | 173 of 674 |
| B | 15 | 1 | 0 | 0 | 0 | 180 | 0 | 33 of 281 |
| C | 31 | 3 | 0 | 0 | 6 | 267 | 1 | 200 of 582 |
| T | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 of 0 |

## Notes

- Super wrote 78 of C's 117 searches (Nano's plan failed in 6 of 9 months).
- Model-written queries were sometimes poor, e.g. arm C, June: "ವಿದ್ಯುತ್ ತರiffe ಜೂನ್ 2026 Karnataka Wisconsin growth"; arm B, January: "बस कि Fahrpreiserhöhung news".
- Arm T: auto_parameters with no dates chose recent windows: time_range w 57, d 14, m 1 of 72 searches (topic, time range, depth → searches: news, w, advanced → 35; news, w, basic → 22; news, d, advanced → 14; general, m, basic → 1); 620 of 659 results were dated October 2026 and 38 undated. Amendment F sends no dates, so every dated result was from the days before the run, after every cutoff, and the verifier rejected all of them: 0 of 29 is the pre-registered result (traces: `audit/arms_traces.md`; this note was corrected from "advanced depth and time_range w for every search", logged, no number changed).
- Median latency was pre-registered as Amendment E metric 4, with no target; it is descriptive only and plays no part in the verdict.
- Credits per known change found (credits ÷ recall) was added after scoring, as a second credit column; it is descriptive and cannot change the verdict.
- Every verified event that matches none of the 29 is listed in `audit/arms_unmatched.md` for a check.
- **Unmatched events, checked by Claude Code against cached text, 10 re-checked live in a browser** (2026-10-25: 9 opened, 1 refused by the browser; `audit/arms_unmatched_check.json`). Of 23: 20 wrong, 3 real change outside the list. Wrong rows by arm: A 8 of 10; B 6 of 7; C 6 of 6. The wrong rows are mostly non-Indian pages, non-domestic or commercial LPG, and lines about a different item. The live re-check overturned one change: Bengaluru Metro's 9 Feb rise was put on hold before it took effect (4 rows).
- **Real changes outside the list** (reported separately; the pre-registered list of 29 and every recall figure are unchanged): 3 rows, 2 distinct changes. Gokul full-cream (buffalo) milk +Rs 2/litre in Mumbai from 21 Feb 2026 (2026-02), found by arm B; MSRTC (Maharashtra state buses) +13.65% permanent fare revision from 17 Jul 2026 (2026-07), found by arm A.

## Exploratory, partial: arm T + dates (added after scoring; cannot change the winner or any verdict)

Same query texts as arm T, `auto_parameters: true`, plus arm A's `start_date`/`end_date` window; no other field from us (dated line in v2/PREREGISTRATION.md). Cap 190 real credits, not raised: 2026-01, 2026-02, 2026-03, 2026-04, 2026-05, 2026-06 complete; 2026-07, 2026-08, 2026-09 incomplete (the cap stopped them).

**Like-for-like (exploratory, partial, added after scoring):** on the 6 complete months, which hold 22 of the 29 known changes, T+dates found 2 and arm A 5. The all-months row below includes the incomplete months.

| Credits spent | Search calls | Verified claims | Distinct verified events | Matched to the 29 | Not matched (unchecked) | Recall | False events (upper bound) | Credits per verified event |
|---|---|---|---|---|---|---|---|---|
| 190 | 56 | 18 | 15 | 2 | 13 | 2 of 29 | 7 of 9 | 12.7 |

**What auto_parameters chose** (topic, depth, time range → searches): news, advanced, w → 38; news, basic, w → 9; news, advanced, d → 7; general, basic, y → 1; news, basic, d → 1.
**Did Tavily keep our dates?** 0 of 56 searches returned only results inside the window with no auto time range; 532 of 532 dated results fell inside the window.
