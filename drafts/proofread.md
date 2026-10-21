# Proof-read before submission

Read on 21 Oct 2026 (main at `9345bdc`), as a judge who has never heard of the project. Files checked: `README.md`,
`docs/devpost_draft.md`, `docs/honest_limits.md`, `docs/video_script.md` and `drafts/judge_faq.md`. Report only:
none of those files is changed here.

**Where numbers were checked:**
- `results/score_lock.json` (the latest score, after the Amendment 3 bug fixes)
- `results/scoreboard.md`, `results/replay.csv`, `results/baselines.csv`, `results/tavily_attribution.csv`
- `results/tavily_report_card.md`, `results/app/flight_recorder.jsonl`
- `docs/after_scoring_changes.md`, `docs/frozen_rules.md`, `audit/*`

## Top 5 issues (fix these first)

1. **README.md is still the day-1 setup page.** It says "Status: foundation (day 1)" and asks the reader to paste
   output "back to Claude". It has no app link, no result and no limits beyond two lines. It also says Tavily reads
   the "government daily retail price tables", which is false (they are downloaded by hand from behind a CAPTCHA).
   Judges open the README first.
2. **The Devpost draft describes a file that does not exist.** "`price_change_radar.py` exposes
   `find_price_changes(...)` and an MCP tool wrapper": no such file or function is in the repo. Remove the line or
   build the file.
3. **The Devpost "Why Tavily" numbers are stale.** They don't match `results/tavily_report_card.md`:
   - calls: 729 → **787**
   - credits per prediction: about 52 (466 in total) → **40.3 (363)**
   - results inside the date window: 74% (1,067 of 1,447) → **77% (1,952 of 2,535)**
4. **`drafts/judge_faq.md` Q4 is now wrong.** I wrote it before Amendment 3. It says "None of it changes a scored
   number" and "We did not go back and fix those events". In fact the audit led to four general bug fixes and one
   logged re-score that moved (c) from 0.185 to 0.194 pp (`docs/after_scoring_changes.md` §4). Q6 can also be filled
   in now (see §1).
5. **The poll comparison is presented unfairly in the video.** Scene 8 puts our 9-month mean miss next to "the
   economists' poll: 0.15", which covers only 6 months. On the same 6 months, (c) is 0.150 and the poll 0.148, so
   they are level. The Devpost draft also says the range is "about −0.14 / +0.33", but the October range a judge
   sees is **± 0.28** (Amendment 2).

## 1. Number check

✓ = matches the source. ✗ = does not match (correct value given). "n/c" = not checkable from repo files.

### README.md

| Number in text | Should come from | Match | Correct value / note |
|---|---|---|---|
| 2,860 markets | MoSPI 2024 series (1,465 rural + 1,395 urban markets; secondary reports) | ✓ | External fact, not in a repo file. Add a source link. |
| 358-item survey | `data/official/README.md` (358 items) | ✓ | |
| 2024-series weights | `docs/frozen_rules.md` | ✓ | |
| Python 3.10, "day 1" | – | ✗ | "Status: foundation (day 1)" is out of date (top issue 1) |

### docs/devpost_draft.md

| Number in text | Should come from | Match | Correct value / note |
|---|---|---|---|
| CPI out "about two weeks after the month ends" | `audit/dates_check.md` (released on the 12th) | ✓ | About 12 days. Fine. |
| 80% range "about −0.14 / +0.33 pp" (10th–90th percentile of 9 misses) | `results/replay.csv` misses of (c): q10 = −0.327, q90 = +0.143 → range −0.14 / +0.33 | ✓ for the pre-registered range | But the live October range is **± 0.284 pp** (Amendment 2, `docs/after_scoring_changes.md`). Say which range the app shows. |
| Inside range in 5 of 9 months | `score_lock.json` `inside_range: 5` | ✓ | |
| 14–21% of basket measured | `replay.csv` `c_coverage_observed` 0.141–0.209 | ✓ | |
| 11% from the spine alone | `replay.csv` `b_coverage_observed` 0.1119 | ✓ | |
| (a) 0.212, 8 of 9 | `score_lock.json` `mae.a` 0.2122, `direction_hits.a` 8 | ✓ | |
| (b) 0.225, 9 of 9 | `mae.b` 0.2249, hits 9 | ✓ | |
| (c) 0.194 (0.185 before), 7 of 9 (8 before) | `mae.c` 0.1937, history 0.1853; hits 7, history 8 | ✓ | |
| B1 0.47, direction "n/a" | `mae.B1` 0.4683; `direction_hits.B1` 0 | ✓ / ✗ | Direction is **0 of 9**, not n/a. B1 repeats last month, so it can never call a change; say that. |
| Poll 0.148, 6 of 6; (c) 0.150 on the same months (0.138 before) | `mae_poll_months` poll 0.1483, c 0.1497, history c 0.1376; `scoreboard.md` direction 6 of 6 | ✓ | |
| GO: B1 0.468, trend 0.212 | `score_lock.json` | ✓ | |
| (c) vs (b): 0.031 pp better (0.225 → 0.194), better in 6 of 9 months | `tavily_attribution.csv`: \|miss_with\| < \|miss_without\| in Jan, May–Sep = 6 | ✓ | 0.2249 − 0.1937 = 0.031 |
| Coverage 11% → 14–21% | `replay.csv` | ✓ | |
| Up to 2 follow-up searches | `docs/pipeline.md` | ✓ | |
| 729 Tavily calls sent | `tavily_report_card.md`: 787 uncached | ✗ | **787** (plus 4,572 served from cache) |
| 222 dated searches for the test months | not in the report card | n/c | Remove, or add it to the card |
| About 52 credits per prediction (466 for 9 months) | `tavily_report_card.md` 40.3; `tavily_attribution.csv` credits sum 363 | ✗ | **About 40 (363 for the 9 replay months)** |
| 74% inside date window (1,067 of 1,447) | `tavily_report_card.md` | ✗ | **77% (1,952 of 2,535; 577 undated)** |
| 91 of 93 quotes verified | `tavily_report_card.md` (98%) | ✓ | |
| 3 of 12 events confirmed by 2 sources | `tavily_report_card.md` | ✓ but stale | Counted before Amendment 3; 9 events remain now. Card also says 5 of 12 had a confirming chase result. |
| 4.3 s median latency | report card; `results/app/flight_recorder.jsonl` 4.29 s | ✓ | |
| 1 fallback, 148 MoSPI API calls, 5 spine requests | report card: 154 direct calls in all; flight recorder: 154 uncached `direct` | ✓ | 1 + 148 + 5 = 154 |
| 0.225 → 0.194 pp, closer in 6 of 9 (attribution) | `tavily_attribution.csv` | ✓ | |
| 1,341 Nemotron calls, median 1.6 s | `results/app/flight_recorder.jsonl`: 1,341 uncached `nebius`, median 1.56 s | ✓ | |
| Seal before 12 Nov; November likely Mon 14 Dec | `audit/dates_check.md` | ✓ | |
| `seal-2026-10`, SHA-256 [TBD] | `sealed/` is empty today | – | Fill in at sealing |

### docs/honest_limits.md

| Number in text | Should come from | Match | Correct value / note |
|---|---|---|---|
| 5 zones; zone-level since Sep 2023 | `docs/frozen_rules.md` §6 | ✓ | |
| Rice R² 0.03 | `docs/frozen_rules.md` §6 | ✓ | |
| 9 test months | `replay.csv` | ✓ | |
| Poll 0.148 on 6 months; (c) 0.150 (0.138 before) | `score_lock.json` | ✓ | |
| (c) 0.194 over 9 months (0.185 before) | `score_lock.json` | ✓ | |
| B2 0.21; B1 0.47 | `score_lock.json` 0.212 / 0.468 | ✓ | |
| 14–21% measured | `replay.csv` | ✓ | |
| Inside range 5 of 9 | `score_lock.json` | ✓ | |
| Live range ± 0.28 pp | `after_scoring_changes.md` ± 0.284 | ✓ | |
| (c) under-predicted in 7 of 9 months | `replay.csv`: negative misses Jan–Jul = 7 | ✓ | |
| 6.0% = RBI's Q3 projection | `audit/dates_check.md` | ✓ | |
| (b) 0.225 vs trend 0.212 | `score_lock.json` | ✓ | |
| Gujarat about 7% of milk spending | MoSPI state weights (`data/official/mospi_cpi2024_weights_Annex_5.3.xlsx`) | n/c | Not checked |
| Audit: 5 / 3 / 3 / 1; 9 second sources | `audit/event_audit.md`, `results/app/audit_summary.json` | ✓ | |
| "whether each quote is on its page was checked for only one row" | `audit/event_audit.md` on branch `eshan/quote-check` (PR bhavikjain026/shadow-cpi#6) | ✗ once PR #6 is merged | **9 of 12 verified on the page** (1 paywalled, 2 pages unavailable); page dates match in 7 of 10 checkable |
| After the fixes, 9 events; (c) 0.194 | `after_scoring_changes.md` §4 | ✓ | |
| 2026-07-E1: "Rs 3 or Rs 4" | the manual check (PR #6) found the cited page says toned milk Rs 54 → 57 | partly | The cited page itself says **Rs 3**. Other outlets say Rs 4. |
| Possible misses: 19 May fuel, Sanchi 15 May, Gokul 21 May | `audit/event_audit.md` | ✓ | The full recall result (9 of 29) is missing here; see §2 |

### docs/video_script.md

| Number in text | Should come from | Match | Correct value / note |
|---|---|---|---|
| 12 Nov release | `audit/dates_check.md` | ✓ | |
| "~2 weeks after the month ends" | `audit/dates_check.md` | ✓ | |
| Poll "0.15" | `score_lock.json` 0.148 | ✓ | But it covers 6 months, not 9 (top issue 5) |
| Scene 7: "[TBD] percent of the basket" | October nowcast file (not built yet) | – | Read off the app. Replay months were 14–21%. |
| Scene 8: mean miss [TBD] | `score_lock.json` | – | **0.19 points** (0.194) over 9 months |
| Scene 8: inside range [TBD] of 9 | `score_lock.json` | – | **5** of 9 |
| Scene 9: worst miss [TBD] | `replay.csv` (largest \|c − actual\|) | – | **February 2026, 0.38 points** (2.83 vs 3.21). The reason is not in `replay.csv` (note is blank). |
| 2:45 total, 140 words/min | – | n/c | Time it on recording day |

### drafts/judge_faq.md

| Number in text | Should come from | Match | Correct value / note |
|---|---|---|---|
| 9 test months; 14–21%; 5 of 9 | `score_lock.json`, `replay.csv` | ✓ | |
| Q6 [TBD] | `score_lock.json` | – | On the 6 dated poll months: **poll 0.148, (c) 0.150, level**. Over all 9 months: (c) 0.194, trend 0.212, B1 0.468. |
| Q4 "None of it changes a scored number" | `after_scoring_changes.md` §4 | ✗ | Amendment 3 moved (c) from 0.185 to 0.194 and direction from 8 to 7 |

## 2. Contradictions between the files

| # | Says | But | Fix |
|---|---|---|---|
| 1 | README: Tavily reads "government daily retail price tables (Extract)" | honest_limits, Devpost and the FAQ: the spine is downloaded by hand from behind a CAPTCHA, and the site blocks Tavily | Rewrite the README bullet |
| 2 | README: "Status: foundation (day 1)" | Every other file describes a finished, scored replay | Update the README |
| 3 | Devpost "What it does": range "about −0.14 / +0.33" | honest_limits: the live October/November range is ± 0.28 (Amendment 2), and that's what the app shows | Give the ± 0.28 range for October. Mention the pre-registered range only as history. |
| 4 | FAQ Q4: "did not go back and fix those events"; "none of it changes a scored number" | honest_limits and `after_scoring_changes.md` §4: four general bug fixes, re-scored once, (c) 0.185 → 0.194 | Rewrite Q4 (suggested text below) |
| 5 | Devpost step 4 and video scene 6: the event layer finds "LPG revisions" | `frozen_rules.md` Amendment 1 (a): LPG events are switched off; LPG comes only from IOCL's list | Say "milk, electricity, rail…", and "LPG from IOCL's official price list" |
| 6 | Video scene 6: shows a milk price change as an event that drives the number | `preregistration.md`: milk events are never applied, because milk comes from the spine | Use an electricity tariff example (e.g. J&K +6.83%, 1 Sep), which is applied |
| 7 | Devpost: Map + Crawl "read official circulars"; "evidence chasing confirms each change with a second source" | Report card: Map + Crawl results are "reported, not used"; 0 verified events. Chasing ran after scoring; 3 of 12 events had 2 sources, 5 of 12 a chase match. | Describe both as extras, not as inputs to the number |
| 8 | Devpost and video: "test months never used for tuning" / "without tuning on those months" | Amendment 3 changed rules after scoring (logged bug fixes, re-scored once) | "Rules frozen before scoring; one logged bug-fix re-score after an independent audit" |
| 9 | FAQ Q3: "Every search is limited to the target month" | `frozen_rules.md` §1: two windows, the month plus the last 10 days of the previous month | Add "plus the 10 days before it, for announcements" |
| 10 | honest_limits: quote-on-page checked for one row only | PR bhavikjain026/shadow-cpi#6 (manual Chrome check): 9 of 12 | Update after PR #6 is merged |
| 11 | Devpost "Why Tavily" figures | `results/tavily_report_card.md` | See §1 (787 calls; about 40 credits; 77%) |
| 12 | The app's audit box (`results/app/audit_summary.json`) shows recall 9 of 29 (14 of 29 counting official series) | honest_limits and the Devpost draft never mention recall | Add one line to honest_limits: "A recall check found 9 of 29 known retail price changes (14 of 29 counting official price lists); electricity and bus fares are the biggest gaps." |

Suggested FAQ Q4 text: "No tuning. Factors were fitted on 2025, and the rules were frozen before any test month was
scored. After scoring, an independent audit found four bugs: wholesale prices, premium fuel, a single heritage
railway treated as national, and a double count. They were fixed as general rules, logged, and re-scored once.
That made our result slightly *worse* (0.185 → 0.194 pp), and we report the worse number."

## 3. Jargon a judge won't understand

| Term | Where | Plain-English replacement |
|---|---|---|
| nowcast / experimental nowcast | everywhere | "an estimate of this month's figure, made before it is published" (keep "experimental") |
| YoY / year-on-year | everywhere | "compared with the same month last year" |
| pp / percentage points | Devpost, honest_limits | "points" (e.g. "off by 0.19 points"); explain once: "4.8% vs 5.0% is 0.2 points" |
| spine / government price spine | all | "the government's daily retail food prices" |
| carried on trend | all | "assumed to keep moving as it has in recent months" |
| coverage | all | "share of the shopping basket we actually measured this month" |
| carve-out / "tracked items move only their own weight" | README, Devpost, honest_limits | "each measured item affects the total only in proportion to its share of household spending" |
| (a), (b), (c), (c-strict) | Devpost, FAQ | "trend only", "government food prices only", "full method (government prices + web evidence)", "full method, official price lists only" |
| B1 / B2 | Devpost, honest_limits | "last month's rate" / "trend only" |
| pass-through factor | honest_limits | "how much of a price change shows up in the official index (fitted on 2025)" |
| leave-one-out, q10/q90, 10th–90th percentile | Devpost, honest_limits | "range built from our misses in the other 8 test months" |
| 80% range | all | "the range we expect the real figure to fall in about 8 times out of 10" |
| out-of-sample | Devpost | "tested on months it was not built on" |
| pre-registered / Amendment 1–3 | honest_limits, FAQ | "rules written down and committed before scoring" / "logged rule change" |
| seal, canonical JSON, SHA-256, git tag | README, Devpost, video | "locked: we publish a fingerprint of the file, so any later change would show" |
| flight recorder | Devpost, video | "a log of every outside call: what was asked, what came back, cost and time" |
| credits, cached | Devpost, video | "Tavily usage units" / "re-used from an earlier call, at no cost" |
| Extract, Map + Crawl, include_domains_mode="prefer" | README, Devpost | "read a page", "list and read pages on an official site", "prefer Indian news sites" |
| event layer, effective date | Devpost, video | "announced price changes, and the date they start" |
| leak guard | Devpost, FAQ | "a filter that drops any page already stating the official figure" |
| index levels, 2024-series weights | README, Devpost | "official index values and each item's official share of spending (2024 basket)" |
| composite item, sub-class | honest_limits | "MoSPI's 'gold' item is really gold, diamond and platinum jewellery" (already explained; keep) |
| R² | honest_limits | "how well it tracked the official index in 2025 (0 = not at all, 1 = perfectly)" |
| MoSPI, DoCA, IBJA, IOCL, PPAC, RBI, MPC, FPPAS | all | Spell each out once: MoSPI (the statistics ministry), DoCA (Department of Consumer Affairs), IBJA (India Bullion and Jewellers Association), IOCL (Indian Oil), PPAC (the oil ministry's price cell), RBI (Reserve Bank of India) |
| Token Factory | README, Devpost | "Nebius Token Factory (the hosted service that runs the Nemotron models)" |
| gatekeeper model, JSON mode, MCP | Devpost | "a small model that only answers yes/no: does this page give an Indian price?"; drop JSON mode and MCP from the main text |
| GO / NO-GO | Devpost | "the pass/fail test we set before scoring" |

## 4. Claims that overstate the results

| # | Claim | Where | Why it overstates | Safer wording |
|---|---|---|---|---|
| 1 | "Token Factory reasons. Tavily knows." | README | Nemotron only extracts and code decides; "reasons" contradicts the project's own rule. "Knows" is hype. | Drop it, or: "Tavily finds the evidence. Nemotron reads it. Code does the maths." |
| 2 | "with a source behind every input" | README, Devpost one-liner | 79–86% of the basket is carried on trend, with no web source | "with a source behind every measured price" |
| 3 | "MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web." | README, Devpost | Implies equal coverage; we measure 14–21% of the basket | Keep it as a hook only with the next sentence: "We can measure about a fifth of the basket this way, and we show how much." |
| 4 | Video scene 8: "Does it work? … Mean miss: [x] points. The economists' poll: 0.15." | video | Compares 9 months with 6. On the same 6 months we are level with the poll (0.150 vs 0.148). | "On the six months with a published poll, we were level with the economists: 0.15 points each. Across all nine months we missed by 0.19 points on average, a little better than simply extending the trend (0.21)." |
| 5 | "evidence chasing confirms each change with a second source" | Devpost step 4 | Only 3 of 12 had 2 sources; chasing ran after scoring and is a text match, not a verified quote | "evidence chasing looks for the same change elsewhere (it found a match for 5 of 12)" |
| 6 | "Tavily Map + Crawl read official circulars" | Devpost step 4, "Why Tavily", video scene 4 | Map returned 0 addresses on all 4 government sites; 0 verified events; not used in the number | "We also tried Map + Crawl on official sites. It found little (results in the report card), so it doesn't feed the number." |
| 7 | "Event layer packaged for reuse: `price_change_radar.py` … MCP tool wrapper" | Devpost | The file does not exist | Remove |
| 8 | "Tavily evidence lowered the mean miss from 0.225 to 0.194 pp" | Devpost | True, but 9 months; `honest_limits` says such differences "may be luck" | Add "over 9 months, a small difference that could be luck" |
| 9 | FAQ Q1: "The gain over trend is real but modest" | judge_faq | 0.212 → 0.194 pp over 9 months can't be shown to be "real" | "The gain over trend is small (0.21 → 0.19 points) and, with 9 months, may be luck." |
| 10 | "Replay results (… test months never used for tuning)" | Devpost heading | One logged bug-fix re-score after scoring | "rules frozen before scoring; one logged bug-fix re-score (Amendment 3)" |
| 11 | Video scene 1: "everyone can see how close we got" | video | Fine, but pair it with the range | "…how close we got, and whether the real number lands inside our range" |
| 12 | Video scene 5: "Click one link to show the same line on the source page" | video | Some source pages are paywalled or blocked (PR #6: 1 paywalled, 2 unavailable) | Pick a page that opens without a login, e.g. the 26 Mar MP electricity article or the 24 Aug J&K one |

## 5. The 5 sentences a judge is most likely to read first

1. **README headline** (the first line on GitHub)
   - Now: "An experimental, sealed nowcast of India's next official CPI inflation number — made before MoSPI releases
     it, with a source behind every input, locked in public, and scored when the real number comes out."
   - Clearer: "Shadow CPI estimates India's official inflation rate before the government publishes it, shows the
     price evidence behind every measured item, and locks each estimate in public so it can be scored against the
     real number."
2. **README tagline**
   - Now: "MoSPI sends price collectors to 2,860 markets. Shadow CPI sends Tavily to the web. Token Factory reasons.
     Tavily knows."
   - Clearer: "The government collects prices in 2,860 markets. Shadow CPI reads dated price news and official price
     lists on the web through Tavily, measures what it can (about a fifth of the basket), and says plainly what it
     can't."
3. **README status line**
   - Now: "Status: foundation (day 1). Built for the Nebius x NVIDIA Global AI Hackathon, 2026."
   - Clearer: "Status: Jan–Sep 2026 replay scored (average miss 0.19 points; level with economists on the 6 months
     they published); October 2026 estimate sealed on [date], to be scored on 12 Nov. Live app: [URL]."
4. **Devpost "What it does", first bullet**
   - Now: "Shows an **experimental nowcast** of the coming month's CPI inflation (year-on-year), with an 80% range
     taken from the replay misses: about −0.14 / +0.33 percentage points around the nowcast…"
   - Clearer: "Shows our estimate of this month's inflation rate (compared with a year ago) and a range of ± 0.28
     points around it. In testing, the real figure fell inside our original, narrower range in only 5 of 9 months,
     so we widened it for October."
5. **Video opening line (scene 1)**
   - Now: "This is our experimental nowcast of India's October inflation. It's sealed and waiting. On the twelfth of
     November the government publishes the real number, and then everyone can see how close we got."
   - Clearer: "This is our estimate of India's October inflation, made before the official figure. It's locked: we
     can't change it. On the twelfth of November the government publishes the real number, and everyone can see how
     close we got."
