# Date test replication: pre-registration

**Written 2026-10-28T13:47Z (UTC), committed before any code for the run is merged and before any search.** Decided
by the owner (task card of 2026-10-28). Docs only: no Tavily call is made on 2026-10-28. Code: `v2/replication.py`,
tests `tests/test_v2_replication.py`, on branch `replication` (not merged on 2026-10-28). Run once with
`python -m v2.replication`; the result file refuses a second run. **Exploratory**: it changes no scored verdict, v1,
the v2 locks or the October seal.

**Question.** On cases the pilots never saw, does a Tavily search with no dates (A) return pages published after
the cutoff, and do `start_date`/`end_date` + `filter_by_published_date` (C) keep them out?

## Cases: source, eligibility, sampling (fixed now)

Target **N = 60** new cases, drawn with seed **20261028** (`random.Random(20261028).sample`) if more than 60 are
eligible; **if 60 or fewer are eligible, all are taken.** A case is excluded if it is one of the date test's 20
(`v2/date_test_cases.json`) or any timelock34 case (`benchmarks/timelock34/cases.jsonl`: the date test's 20 + the
finance check's 14).

**Sources, read in this order (all already in the repo, read on 2026-10-28):**

1. **Hand-built reference** `v2/recall_reference.json` (29 changes, transcribed from `audit/missed_events.md`).
   Eligible: a day-level `date` from 2026-01-01 to 2026-09-30 and not excluded. Each row is its own event.
2. **Verified price events** in `v2/evidence/events_2026-01.json` … `events_2026-09.json` and
   `v2/ablation/arm_*_2026-0[1-9].json`. Eligible: the card's and the claim's `status` both `verified`; an
   `effective_date` written `YYYY-MM-DD`, from 2026-01-01 to 2026-09-30; a kind with a query template (milk,
   electricity, lpg, petrol/diesel = fuel, rail, bus, metro); and a place in India (the claim names states, or its
   region contains "india", "nationwide" or "national"). Records are read in the order (date, kind, file, address,
   states).
3. **Finance events** `v2/FINANCE_PREREG.md` (Amendment 1, the 14 in `v2/finance_lookahead.py`). All 14 are timelock34
   cases, so **0 are eligible**. No other finance event list with official dates is in the repo; none is added.

**v1's kept events** (`data/evidence/2026-0*_trace.json`, verdict "kept") are not a separate source: the hand-built
reference already lists every one of them (its v1 = FOUND column). Checked on 2026-10-28: each kept event with a
`YYYY-MM-DD` date (Amul/Mother Dairy 14 May, fuel 15 May, UPPCL 1 Jun, J&K 1 Sep) matches a reference row.

**Same event.** A source-2 record is the same event as a reference row (any of the 29, pilot or not) or an earlier
kept source-2 record when: same kind, overlapping place (either is national, i.e. names no state, or they share a
state), and dates within **7 days** (the same month when either has no day). It is then dropped, with the reason
logged in `v2/replication_cases.json`. Reference rows are never merged with each other.

**Per case.** Cutoff = **the day before the event**. One frozen English query, the date test's template: the
item's words + place + the event's month (place = the states, as the date test writes them, or "India" if none).
The date test had no template for metro; it is `metro fare hike`.

**Result of the rule (offline, `python -m v2.replication --plan`, 0 calls): 22 eligible, fewer than 60, so all 22
are taken.** 22 are price cases (date-test rule) and 0 finance cases. 108 records were dropped (20 reference rows
that are pilot cases, 14 finance events in timelock34, 74 source-2 records that repeat an event). Frozen in
`v2/replication_cases.json`:

| Case | Kind | Event | Cutoff | Arm C window | Query | Source |
|---|---|---|---|---|---|---|
| VE01 | fuel | 2026-01-01 | 2025-12-31 | 2025-12-02 → 2025-12-31 | petrol diesel price hike India January 2026 | ablation arm_A_2026-01 (aajtak.in) |
| VE02 | lpg | 2026-01-01 | 2025-12-31 | 2025-12-02 → 2025-12-31 | LPG cylinder price hike Delhi January 2026 | ablation arm_B_2026-01 (aajtak.in) |
| VE03 | lpg | 2026-02-01 | 2026-01-31 | 2026-01-02 → 2026-01-31 | LPG cylinder price hike Maharashtra February 2026 | ablation arm_Td_2026-02 (navbharattimes) |
| VE04 | metro | 2026-02-09 | 2026-02-08 | 2026-01-10 → 2026-02-08 | metro fare hike Karnataka, Delhi February 2026 | ablation arm_A_2026-02 (moneycontrol.com) |
| RR-T1 | rail | 2026-02-21 | 2026-02-20 | 2026-01-22 → 2026-02-20 | rail fare hike Tamil Nadu February 2026 | reference T1 |
| RR-M1 | milk | 2026-02-28 | 2026-02-27 | 2026-01-29 → 2026-02-27 | milk price hike Maharashtra February 2026 | reference M1 |
| RR-L1 | lpg | 2026-03-07 | 2026-03-06 | 2026-02-05 → 2026-03-06 | LPG cylinder price hike India March 2026 | reference L1 |
| VE05 | lpg | 2026-03-20 | 2026-03-19 | 2026-02-18 → 2026-03-19 | LPG cylinder price hike India March 2026 | ablation arm_C_2026-03 (indiatv.in) |
| RR-E3 | electricity | 2026-04-01 | 2026-03-31 | 2026-03-02 → 2026-03-31 | electricity tariff hike Punjab April 2026 | reference E3 |
| RR-T2 | bus | 2026-04-15 | 2026-04-14 | 2026-03-16 → 2026-04-14 | bus fare hike Maharashtra April 2026 | reference T2 |
| VE06 | rail | 2026-05-04 | 2026-05-03 | 2026-04-04 → 2026-05-03 | rail fare hike India May 2026 | ablation arm_Td_2026-05 (amny.com) |
| RR-F1 | fuel | 2026-05-15 | 2026-05-14 | 2026-04-15 → 2026-05-14 | petrol diesel price hike India May 2026 | reference F1 |
| RR-F2 | fuel | 2026-05-19 | 2026-05-18 | 2026-04-19 → 2026-05-18 | petrol diesel price hike India May 2026 | reference F2 |
| RR-F4 | fuel | 2026-05-25 | 2026-05-24 | 2026-04-25 → 2026-05-24 | petrol diesel price hike India May 2026 | reference F4 |
| VE07 | bus | 2026-06-12 | 2026-06-11 | 2026-05-13 → 2026-06-11 | bus fare hike Madhya Pradesh, Delhi, Uttar Pradesh June 2026 | ablation arm_H_2026-06 (livehindustan.com) |
| VE08 | lpg | 2026-07-01 | 2026-06-30 | 2026-06-01 → 2026-06-30 | LPG cylinder price hike Delhi July 2026 | ablation arm_A_2026-07 (aajtak.in) |
| VE09 | bus | 2026-07-17 | 2026-07-16 | 2026-06-17 → 2026-07-16 | bus fare hike Maharashtra July 2026 | ablation arm_A_2026-07 (indianexpress.com) |
| VE10 | milk | 2026-07-24 | 2026-07-23 | 2026-06-24 → 2026-07-23 | milk price hike Karnataka July 2026 | ablation arm_H_2026-07 (timesofindia) |
| VE11 | bus | 2026-08-05 | 2026-08-04 | 2026-07-06 → 2026-08-04 | bus fare hike Madhya Pradesh August 2026 | ablation arm_H_2026-08 (abplive.com) |
| RR-M10 | milk | 2026-08-11 | 2026-08-10 | 2026-07-12 → 2026-08-10 | milk price hike Maharashtra August 2026 | reference M10 |
| VE12 | lpg | 2026-09-01 | 2026-08-31 | 2026-08-02 → 2026-08-31 | LPG cylinder price hike Delhi September 2026 | ablation arm_A_2026-09 (aajtak.in) |
| VE13 | rail | 2026-09-01 | 2026-08-31 | 2026-08-02 → 2026-08-31 | rail fare hike Maharashtra September 2026 | ablation arm_B_2026-09 (jansatta.com) |

Full source addresses are in `v2/replication_cases.json`.

**Kept as the rule gives them, logged now:** "verified" means the price is in the cited line, and the kind and place
come from keywords in that line. So some source-2 records describe a different real-world change from the one their
query names: VE03 is a 19 kg (commercial) cylinder; VE05's page is about premium petrol; VE06's page is a US (PATH)
train fare; VE07's page is new city buses; VE10's page is ghee and butter; VE13's page is about milk and LPG. Under
the date-test rule a leak is any page published after the cutoff, whatever the event, so each is still a valid
query-cutoff case. No case is removed or added after this commit. Two groups share a query with different cutoffs
(RR-L1/VE05; RR-F1/F2/F4); they are kept as sampled, as the pilot kept its two shared queries.

**Sensitivity subset (fixed now):** every metric is also reported for the **9 hand-built reference cases** (RR-*)
alone. The primary result is all 22.

## Arms (run close together, in a seeded random order per case, seed 20261029; everything else identical)

Price cases use the date test's common parameters: `topic` news, `search_depth` basic, `max_results` 3,
`include_published_date` true, `include_domains` = the English news list in `shadow_cpi/evidence.py`, mode prefer, no
language. Finance cases (none here) would use the finance check's: `max_results` 5, no domains.
- **A:** no date parameters, `filter_by_published_date` false.
- **C:** `start_date` = cutoff − 29 days, `end_date` = cutoff, `filter_by_published_date` true.

Arms B and D of the date test are not repeated. **No Extract** call is made (Extract was only for D's page-date check).

## Labels: the pilots' leak definitions, applied by case type

- **Price cases, date-test rule** (`v2/DATE_TEST_PREREG.md`, code `v2.date_test.label`): **confirmed leak (L)** =
  the Wayback Machine CDX API lists no capture on or before the cutoff, its first capture is after the cutoff, and
  Tavily's published date or the date in the address is after the cutoff. **P** = a Wayback capture on or before the
  cutoff. **F (date flag)** = a post-cutoff date without that evidence; **U** otherwise. With no Extract, the page
  date is not read, so F uses Tavily's and the address's dates only. **Valid evidence** = a P result whose title or
  snippet names the item.
- **Finance cases, finance rule** (`v2/FINANCE_PREREG.md` Amendment 1, code `v2.finance_lookahead.label`): confirmed
  leak, snippet leak, date flag and valid evidence exactly as written there. (0 cases here.)

Counts are reported **separately per rule and never added across rules.**

## Wayback

Same CDX query as the pilots (`v2.date_test.wayback`, a logged direct download, 0 Tavily credits). **The first pass
is the primary result.** Then, in the same run, lookups that failed (no response) are retried **once** by the
pilots' logged rule (`tools/wayback_retry.py`): only the failed lookups, 3 tries, 5 s apart, same query and labels.
The retry is reported beside the first pass, labelled secondary.

## Metrics (per rule, per arm; n = cases of that rule)

1. **Leak count:** cases with at least one confirmed leak, x of n, **Wilson 95%** interval.
2. **A vs C paired, exact McNemar** (two-sided) on confirmed-leak cases.
3. **Valid evidence lost:** valid results found by either arm and not kept by this arm.
4. Descriptive: confirmed-leak results, date-flag cases, undated results, failed Wayback lookups, credits, median
   latency (Tavily `response_time`).
5. **Secondary, pre-stated:** the pooled pilot + replication count per rule, first passes only: date-test rule =
   the date test's 20 (its arms A and C) + these price cases; finance rule = the finance check's 14 (its N as A, D as
   C) + these finance cases. Wilson 95% and exact McNemar on the pooled pairs. Never added across rules.

## Both outcomes are reported

Whatever happens, the headline says it. **If arm C has a confirmed leak in any case, the headline names the case,
the address, Tavily's date, the first Wayback capture and a quote from the title/snippet.** If C has none, the
headline says 0 of n with its Wilson interval, which with 22 cases is about 0–15%, not "never".

## Output and cap

`results/replication.json` and `results/replication.md`. **Hard cap 200 Tavily credits** (`replication` in
`config/budget.json`, added on branch `replication` with the code). Estimate: **44 credits** (22 cases × 2 arms × 1
basic search); Extract 0; Wayback 0 Tavily credits. **Nemotron: 0 calls**; both leak rules are code-only (dates,
Wayback and fixed word lists). A cap stops the run cleanly and marks it incomplete. The run checks that
`v2/replication_cases.json` still equals what this rule produces, and refuses to run otherwise.
