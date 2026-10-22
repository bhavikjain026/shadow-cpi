# Search-parameter ablation (Amendments E and F)

**DEVELOPMENT data**, Jan–Sep 2026. Metrics computed once, 2026-10-22T11:26 UTC (commit 5b1eec0); this page re-presents them with corrected labels (see the label fix below). Matcher unchanged since db2984c; 29 known changes.

## Reconciliation (every number below comes from this table)

| Arm | Credits spent | Search calls | Verified claims | Distinct verified events | Events matched to the 29 | Not matched (unchecked; may include real changes missing from the 29) | Recall (of the 29) |
|---|---|---|---|---|---|---|---|
| A | 205 | 117 | 27 | 16 | 6 | 10 | 6 of 29 |
| B | 117 | 72 | 10 | 9 | 2 | 7 | 2 of 29 |
| C | 184 | 117 | 11 | 8 | 2 | 6 | 2 of 29 |
| T | 121 | 72 | 0 | 0 | 0 | 0 | 0 of 29 |

- **Distinct verified event:** a distinct (item, effective date, set of states) among an arm's verified claims. **Recall** counts the 29 known changes found by any verified claim; one event can match one change and several pages can report it, so recall and matched events differ.
- **False events (upper bound)** = verified events of an item that moves CPI by itself (electricity, diesel, bus, rail, mobile) that match none of the 29, out of all such events (pre-registered, Amendment E metric 2). Milk, LPG and petrol events are left out because their spine or official series moves the number.
- **Credits per verified event** = credits spent ÷ distinct verified events of any item (Amendment E metric 3).

## Result

| Arm | Searches written by | Recall | False events (upper bound): unmatched of CPI-moving events | Credits per verified event | Credits per known change found (added after scoring; descriptive) | Median Tavily latency (descriptive; pre-registered with no target, not used in the verdict) | Incomplete months |
|---|---|---|---|---|---|---|---|
| A | code (fixed templates) (en, hi, mr, ta, te, kn, bn) | 6 of 29 | 6 of 8 | 12.8 (205 ÷ 16) | 34.2 (205 ÷ 6) | 3.12 s | none |
| B | Nemotron (en, hi) | 2 of 29 | 2 of 3 | 13.0 (117 ÷ 9) | 58.5 (117 ÷ 2) | 3.12 s | none |
| C | Nemotron (en, hi, mr, ta, te, kn, bn) | 2 of 29 | 1 of 1 | 23.0 (184 ÷ 8) | 92.0 (184 ÷ 2) | 3.15 s | none |
| T | Tavily auto_parameters (B's query texts) (en, hi) | 0 of 29 | 0 of 0 | — (121 ÷ 0) | — (121 ÷ 0) | 6.30 s | none |

**Verdict (Amendment F, margin ±1 known change), unchanged:** top group A; ranking A; lower recall B, C, T.

Arm A's credits are those of its calls when first made, in the issue 4 and issue 14 runs: the flight recorder has 213 uncached Tavily calls tagged `v2:events`, 205 credits, equal to the credit ledger's `v2-issue4` (150) + `v2-issue14` (55). Arm A itself re-ran them from the cache at 0 new credits.

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
- Arm T: Tavily's auto_parameters chose `time_range: "w"` (the past week), topic news and advanced depth for every search. Amendment F sends no dates, so every result was from October 2026, after every cutoff, and the verifier rejected all of them: 0 of 29 is the pre-registered result.
- Median latency was pre-registered as Amendment E metric 4, with no target; it is descriptive only and plays no part in the verdict.
- Credits per known change found (credits ÷ recall) was added after scoring, as a second credit column; it is descriptive and cannot change the verdict.
- Every verified event that matches none of the 29 is listed in `audit/arms_unmatched.md` for a hand check.
