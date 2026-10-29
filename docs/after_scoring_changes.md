# Changes made after scoring

The replay (Jan–Sep 2026) was scored once on 2026-10-21 (`results/score_lock.json`). Every change made after that
is listed here with its date, reason and commit. None of them changes a scored result.

- **2026-10-21 · commit `7b3f138`** · Record-only fix: announced_date in 7 test-month manifests (Feb, Apr–Sep; the
  June file already held an ISO date, so 6 files changed). No decision logic reads it; score_lock.json unchanged
  (c = 0.185 pp); March rebuild test passes (`tests/test_build_nowcast.py`, committed separately).

## 1. Amendment 2: wider 80% range and P(headline ≥ 6.0%), live months only

- **Date:** 2026-10-21
- **Decided by:** the owner
- **Reason:** the pre-registered leave-one-out 80% range held the official figure in only 5 of 9 scored months,
  so it is too narrow to seal. The scored months keep their original ranges and the 5-of-9 figure.
- **Change:** for 2026-10 and 2026-11 only, the 80% range is the prediction ± the 80th percentile of |miss| of (c)
  over the 9 scored months, never narrower than the pre-registered range. P(headline ≥ 6.0%) is added from the same
  range (normal, central 80% = the range). 6.0% is the RBI's Q3 projection. Full text: `docs/frozen_rules.md`,
  Amendment 2. Code: `shadow_cpi/live_range.py`; tests: `tests/test_build_nowcast.py`.
- **Effect on October (dry run, 2026-10-21):** width 0.568 pp (± 0.284) instead of 0.470 pp. The new range is
  centred on the prediction; the pre-registered one sat above it, because (c) under-predicted in 7 of 9 months.
- **Commit:** `afc2241`

## 2. October builder (`build_nowcast.py`) and a reusable observed-series step

- **Date:** 2026-10-21
- **Reason:** the seal needs `results/nowcast_<month>.json` from the same code that was scored.
- **Change:** `build_nowcast.py <month> --cutoff <date>` calls `shadow_cpi.predict.predict_month(month, "c", ...)`
  (the scored function, not a copy). The gold/silver/LPG/petrol step of `run_replay_layers.py` was moved, unchanged,
  into `observed_layers()` and `cached_lpg_petrol()` so the builder and the replay share it.
- **Check:** rebuilt from cache, all 9 scored months reproduce their scored (c) number exactly (bit for bit);
  March is a permanent test (`test_builder_reproduces_scored_march_exactly`).
- **Needs the owner's OK — IOCL gap and the cutoff:** Amendment 1 (a) records an LPG gap when IOCL's list was saved
  before the month's data. The replay compared with the month end. For a live month, the builder compares with the
  evidence cutoff instead (min(month end, cutoff)), because a list saved on 29 Oct can never be dated after 31 Oct
  before the seal. For the 9 scored months this gives the same answer (checked). If the owner prefers the month-end
  reading, October LPG is always a gap and follows trend.
- **Approved by the owner on 2026-10-21**, on the condition that the IOCL list used shows the price in effect during
  the target month. How it is met: the list counts only if retrieved on or after min(month end, cutoff), so it holds
  every revision in force up to the cutoff; otherwise the month is an LPG gap. The builder writes the row in force and
  the list's retrieval time to `inputs.iocl_row_in_force` in the nowcast file, so the condition can be checked.
- **Commit:** `afc2241`

## 3. March manifest quotes restored (data only)

- **Date:** 2026-10-21
- **Reason:** the events-only test-month re-runs (`d44aead` onwards) rewrote `manifests/2026-03.json` with 38 of the
  50 verified quotes from Prompt 2, so the Evidence page lost 12 of them (6 tomato, 3 onion, 3 LPG).
- **Change:** the `quotes` list was copied back from commit `f00bd45` (50 quotes; the 38 already there are
  unchanged); `detail.quotes_restored_from` says so. No logic changed. The predictor reads only the manifest's
  `events`, which are unchanged, so no scored number moves (the builder check above confirms it).
- **Commit:** `620a8e8`

## 4. Amendment 3: bug fixes found by the independent audit (re-scored once)

- **Date:** 2026-10-21
- **Decided by:** the owner, after Eshan's independent audit (PR #4, `audit/event_audit.md`: 5 correct, 3 partly,
  3 wrong, 1 unclear; 9 confirmed by a second source).
- **Rule followed:** the pre-registered "change nothing except genuine bugs; log each one; report scores before and
  after". Every fix is a **general** rule that enforces scope already written in `docs/frozen_rules.md` (retail only,
  the CPI variety, correct geography, no double counting). No month- or event-specific patch, no hand-edited event.
  Code: `shadow_cpi/event_rules.py`, `shadow_cpi/evidence.py` (`judge_event`, `line_context`); tests:
  `tests/test_amend3.py`, `tests/test_spine.py`.

| Fix | General rule | Scope rule it enforces | Audit row |
|---|---|---|---|
| a | Retail only: wholesale, tabela, loose and dairy-farmer-rate wording (procurement/purchase price, paid to farmers) in English, Hindi and Marathi. In the cited line it always drops the event; in the line's context (the sentences just before and after it, and the page title) it drops the event when the line itself names no retail price. | frozen_rules §5, Amendment 1 (d): retail only | 2026-09-E1 (Mumbai wholesale buffalo milk) |
| b | Fuel variety: premium or branded grades (XP95, XP100, Xtra Green/Premium, Speed, Power, premium, branded, all languages) are not the CPI's regular petrol/diesel. | §3.1: the CPI variety | 2026-04-E4 (XP100, Xtra Green) |
| c | Geography: an event is national only if its cited line says nationwide, or a national body/operator sets an all-India price (oil companies, Railway Board, TRAI and telcos, NPPA, GST Council). A single line, route, zone, metro or district is regional, weighted by its state's share. | §4: national vs regional scope | 2026-02-E1 (Nilgiri Mountain Railway) |
| d | Double counting: at most one event per kind × state(s) × month. Several are merged into one: median % change, earliest effective date (day share recomputed). | §4: duplicates are one event | 2026-04-E1/E2 (MP milk, Indore + Dhar) |

**2025 re-check (cache only, 0 credits):** recall stays **3 of 4**. Nothing gained, nothing lost: all 7 kept 2025
events are identical (kind, scope, states, change, date, source). Files: `results/recall_audit/amend3_*`.

**Control run first:** re-running Jan–Sep from cache with the code *before* the fixes reproduced all 12 events
exactly (`logs/replay_amend3_control.txt`, kept locally), so every difference below comes from the fixes.

**Events per month, before → after** (cache only, 0 credits; `logs/replay_amend3.txt`, kept locally):

| Month | Before | After |
|---|---|---|
| 2026-01 | 0 | 0 |
| 2026-02 | rail, national, +5.96% | rail, **Tamil Nadu** (weight 0.097), +5.96% (c) |
| 2026-03 | 0 | 0 |
| 2026-04 | MP milk +4.97%, MP milk +6.63%, MP electricity +4.80%, fuel (premium) +1.64% | MP milk **+5.80%** (one event, median, d), MP electricity +4.80% (b drops the premium fuel row) |
| 2026-05 | milk national +3.30%, fuel +3.29% | unchanged |
| 2026-06 | UP electricity +10% | unchanged |
| 2026-07 | TN milk +4.88% | unchanged |
| 2026-08 | Maharashtra milk +3.24% | unchanged |
| 2026-09 | milk MH+Delhi +14.57%, J&K electricity +6.83% | J&K electricity +6.83% (a drops the wholesale milk row) |
| **Total** | **12** | **9** |

Milk events are recorded but never applied by the predictor (milk is observed through the spine), so fixes (a) and
(d) change the record, not the numbers. Only February (rail) and April (fuel) predictions moved.

**Scores before → after** (re-scored once, `tools/score_replay.py --bugfix ... --cache-only`, 0 credits; the earlier
files are kept as `results/*_before_bugfix_2026-10-21T151419.*` and in `results/score_lock.json` → `history`):

| Method | Mean absolute miss (pp) before | after | Direction right (of 9) before | after |
|---|---|---|---|---|
| (a) Trend only | 0.212 | 0.212 | 8 | 8 |
| (b) Spine only | 0.225 | 0.225 | 9 | 9 |
| **(c) Spine + Tavily** | **0.185** | **0.194** | 8 | 7 |
| (c-strict) | 0.204 | 0.204 | 8 | 8 |
| B1 last month | 0.468 | 0.468 | 0 | 0 |
| Poll months: poll / (c) | 0.148 / 0.138 | 0.148 / 0.150 | | |

- GO rule still met: (c) 0.194 < trend 0.212 and < B1 0.468. On the 6 poll months, (c) no longer beats the poll.
- 80% range: inside in **5 of 9** months, before and after.
- Skeptic: April's new top-3 counter-search was not in the cache, so it was **not run** in the re-score (recorded
  in `results/skeptic_replay.json`). Its count before was 0, so no range changed. Every other month's skeptic
  matched the scored run.
- Amendment 2 October range: unchanged at ± 0.284 pp (the 80th percentile of |miss| still falls between the same
  two months).
- Not tuned further.
- **Commit:** `b88a6fd`

## 5. Needle step jumps on the Live build page (display only)

- **Date:** 2026-10-27
- **Why:** the Live build page and the "What Tavily adds" chart showed each step as the difference between
  successive needle values. Carving an item out of its group swaps the group's trend for the item's own trend, so
  that difference moved even when the evidence equalled the item's trend (the same artefact fixed in the October
  radar's effect formula, `v2/RADAR_PREREG.md` Amendment R2).
- **Change:** each step's jump = needle(with the item's change) − needle(the item carved out on its own trend, no
  change) (`v2.needle.jumps`); a step whose evidence equals the item's own trend shows exactly 0. "What Tavily adds"
  now shows trend only, then each stage's summed jumps (government spine; official series via Tavily Extract;
  announced changes via Tavily Search), then a separate bar for carving measured items out of their groups, so the
  bars still end exactly at the final needle. Items whose measured change is 0% while their own trend rises (LPG,
  petrol in September) now show a real jump: that is evidence, not the artefact.
- **Display only:** the two saved runs were rebuilt offline (`tools/build_needle_jumps.py`, 0 calls), adding only
  `jump_pp` and `adds`. Their needle path is recomputed and checked against the saved values first. No results
  file, seal, score lock or needle value changed: SHA-256 of every file in `results/` and `sealed/` identical before
  and after; every existing field of the run files identical (`tests/test_needle_jumps.py`). Final v2 for
  September 2026 unchanged.
- **2026-10-27, labels (display only):** each Live build step is labelled against its own trend, e.g. "Petrol: 0%
  change, trend expected a rise of 1.4% → −0.067 pp vs. trend", with the caption "Each step is the item's measured
  change minus what its own trend expected." The run files gain only `trend_change` per step (`v2.needle.own_trend`);
  the same hash check passes (`tests/test_needle_jumps.py`).

## 6. New metric: Brier score for P(headline ≥ 6.0%), from October 2026 on

- **Date:** 2026-10-27
- **Decided by:** the owner (task card of 27 Oct).
- **What:** `score.py` adds two columns to `results/archive.csv`: the sealed `p_headline_ge_6` and its Brier score,
  (p − outcome)², where outcome = 1 if the official headline YoY is ≥ 6.0% (`shadow_cpi.live_range.THRESHOLD`,
  RBI's Q3 projection), else 0. Lower is better: 0 is a perfect call, 0.25 is what p = 0.5 always scores.
- **Applies from October 2026 on only** (`score.BRIER_FROM = "2026-10"`). This is a **new metric**, not a re-scoring.
  The scored months Jan–Sep 2026 sealed no probability, and they get no Brier score even if a file carried one. Their
  scores, `results/score_lock.json` and every seal are unchanged.
- **When it first counts:** after MoSPI releases October CPI (12 Nov 2026) and the release line is added to
  `data/official_releases.csv`.
- **Tests:** `tests/test_seal_tools.py::test_brier_from_october_on_only`.

## 7. Forced model migration from 9 Nov 2026 (pre-registered)

- **Date:** 2026-10-27, written 2026-10-27T13:50:34Z (UTC), committed before any code (`v2/PREREGISTRATION.md` Amendment G).
- **Decided by:** the owner (task card of 27 Oct), because Nebius removes both original models.
- **Rule:** "Forced model migration: from 2026-11-09 (IST), calls use Nebius's recommended replacements; prompts, schemas, rules and code are unchanged. The October seal uses the original models. The November seal and any live run during judging use the replacements and say so in their output."

| Role | Original ID (calls dated up to 2026-11-08 IST) | Replacement (calls dated from 2026-11-09 IST) |
|---|---|---|
| Gatekeeper (`small`) | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | `nvidia/Nemotron-3_5-Lightning` |
| Line-citing reader (`mid`) | `nvidia/nemotron-3-super-120b-a12b` | `nvidia/Nemotron-3.5-Super-VL` |

- **What it does not change:** no scored month, `results/score_lock.json`, the October seal or any saved result. Calls
  dated up to 2026-11-08 IST, and any request already in the cache, still use the original models.
- Source: Nebius's notice, docs.tokenfactory.nebius.com/model-deprecations-november-2026 (checked 2026-10-27): the two original IDs are removed from Serverless on 9 Nov 2026; requests are not rerouted automatically.

## 8. Drift monitor: cited lines joined with "[...]" are checked piece by piece (general-rule bug fix)

- **Date:** 2026-10-28
- **Decided by:** the owner (task card of 28 Oct).
- **Bug:** `v2/drift.py` searched a cited line that holds several pieces joined with `[...]` as one string. When the
  pieces sit apart on the page, the joined string is never a substring, so "quote still present" read no and "number
  changed" was taken from a nearest-line guess, both wrongly.
- **Rule (general, all pages):** split the cited line at `[...]`, strip each piece, whitespace-normalise as in
  `v2/DRIFT_PREREG.md` rule 4; the quote is present only if every piece is present. Number changed is read per piece
  and combined (yes if any piece yes, else unknown if any unknown, else no). Clarification appended to
  `v2/DRIFT_PREREG.md`. Tests: `tests/test_v2_drift.py::test_cited_pieces_joined_with_ellipsis_are_each_searched_for`.
- **28 Oct run, recomputed offline (0 credits) from the 13 cached Extract responses (same normalised hashes as the
  saved run, all 62 pages):**

| Of the 14 pages with a changed hash | Before | After |
|---|---|---|
| Cited quote gone | 4 | 1 |
| Cited quote still present | 10 | 13 |
| Number changed: yes | 3 | 0 |
| Number changed: unknown | 1 | 1 |
| Number changed: no | 10 | 13 |

  The 3 pages that moved were all multi-piece lines whose pieces are far apart; the "before" column reproduces the
  committed file exactly. The "changed" (hash) count, 14 of 62, is unchanged. `v2/radar/drift_2026-10.json` holds
  the fixed fields and keeps the old counts under `recomputed_2026-10-28.before`.
- **What it does not change:** no forecast, seal, score, radar tier or radar effect.

## 9. October spine: the partial month is replaced by a later fetch (data-vintage fix, not a rule change)

- **Date:** 2026-10-28
- **Decided by:** the owner (seal-prep task card of 28 Oct).
- **Why:** `seal_checklist.md` §1 asks for a new DoCA fetch for Jan–Oct 2026 before the seal, because "October is a
  partial month (data up to the fetch date)". The 21 Oct files (`2026AB.html`, `2025H2-2026fill.html`) hold October
  month-to-date as of 21 Oct; today's fetch (`2026A.html` + `2026B.html`, all 19 commodities, Jan–Oct 2026, saved
  **2026-10-28 12:23 UTC**, `data/official/doca/raw/fetch_summary.json`) holds it as of 28 Oct. `spine.build()`
  refuses any overlap that disagrees, so it refused October (89 cells).
- **Change:** `shadow_cpi/spine.py` `SUPERSEDED` names the two 21 Oct files and month 2026-10 only, with the reason;
  `build()` skips those months in those files. The raw files are untouched. Every other overlap must still agree
  exactly (it does: Jan–Sep 2026 in the new files equals the old files cell for cell). Tests:
  `tests/test_spine.py::test_superseded_month_is_skipped_only_in_the_named_file`,
  `::test_superseded_names_only_the_21_oct_files_and_october`.
- **Jan–Sep unchanged:** every one of the 981 existing `data/spine.csv` rows for 2026-01..2026-09 is byte-identical;
  SHA-256 of those rows without masoor dal is `81d79d258034038b…` before and after. Dec 2024 – Dec 2025 is
  byte-identical too. Rebuilt from cache, all 9 scored months reproduce their scored (c) and (b) numbers exactly
  (`results/replay_predictions.json`); `results/score_lock.json` is untouched.
- **Masoor dal (new rows only):** the new fetch returned 4 more zones of masoor dal for Jan–Oct 2026 (the 21 Oct
  fetch had 1), so 50 rows are added (4 zones + the all-India mean, 10 months). Masoor dal is not in
  `SPINE_FOODS`; no model, factor or rule reads it. Only the app's Evidence page, which lists the spine rows for a
  month, shows it.
- **October before → after** (all-India simple mean of 5 zones, Rs.; and the Oct-vs-Sep change the model uses,
  geometric mean over zones):

| Spine food | Oct price, 21 Oct fetch | Oct price, 28 Oct fetch | Change used, before | Change used, after |
|---|---|---|---|---|
| Onion | 53.58 | 53.53 | +0.258% | +0.166% |
| Tomato | 42.77 | 42.32 | +6.833% | +5.605% |
| Potato | 22.36 | 22.37 | −0.684% | −0.680% |
| Tur dal | 128.94 | 129.95 | +3.192% | +4.005% |
| Edible oils (6 packed oils pooled) | – | – | +0.640% | +0.800% |
| Rice (spine-use rule: carried on trend) | 46.49 | 46.69 | +1.240% | +1.601% |
| Atta | 41.10 | 41.11 | +0.415% | +0.453% |
| Milk | 62.18 | 62.22 | +0.184% | +0.246% |
| Eggs | 84.51 | 84.60 | −0.030% | +0.078% |

- **What it does not change:** no rule, factor, filter, scored month or replay score. October is still a partial
  month (DoCA data up to 28 Oct, the evidence cutoff day).

## 10. Seal-day note: `run_evidence.py` rewrites `config/passthrough.json` (29 Oct 2026)

`run_evidence.py` rewrites `config/passthrough.json` (drops `use_spine`/`_food_rule`); restored from git before the build; to fix after submission, before the November run. Factor values were identical; the restored file is byte-identical to the committed (frozen) one.
