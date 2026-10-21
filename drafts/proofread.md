# Proof-read before submission (round 2)

Read on 22 Oct 2026, as a judge who has never heard of the project. It covers main at `961cca0` (Bhavik's docs
sprint) plus PR bhavikjain026/shadow-cpi#8 (docs round 2, which includes PR #6). Files read:
- `README.md`
- `docs/devpost_draft.md`
- `docs/honest_limits.md`
- `docs/video_script.md`
- `drafts/judge_faq.md`

Report only: none of those files is changed here. This replaces the first proof-read, which covered the files
before the sprint. Most of its findings are now fixed, including the dead `price_change_radar` line, the stale
Tavily numbers, the README rewrite, the FAQ Q4 contradiction (PR #8), and the poll comparison in the video.

**Where numbers were checked:**
- `results/score_lock.json`, `results/scoreboard.md`, `results/replay.csv`, `results/tavily_attribution.csv`
- `results/tavily_report_card.md`, `results/app/flight_recorder.jsonl`, `results/app/tavily_trace_2026-03.json`
- `config/models.json`, `config/budget.json`, `docs/after_scoring_changes.md`, `audit/*`

**Code links:** every README link to a line of code (pinned at `9345bdc`) was opened, and each points at the right
line. The links are listed in §1.

## Top 5 issues

1. **The "one miss explained" is not a miss.** The Replay page and video scene 9 explain **January**. The app picks
   it only because it's the one month with a written note (`app_pages/replay.py` line 102: `max(noted or replay, …)`).
   January's estimate was off by 0.17 points and landed *inside* the range. The biggest miss was **February: 0.38
   points, outside the range** (2.83 vs 3.21, `results/replay.csv`), and it has no explanation. A judge may read this
   as picking the flattering month. Fix one of two ways: write notes for the out-of-range months (Feb, Mar, Aug,
   Sep) and let the page show February, or rename the section "One month explained" and change the video line to
   match. A note is plain text, not a number, but it lives in a scored results file, so Bhavik should decide.
2. **The FAQ says searches stay inside the month, but they don't.** Q3 says "Every search is limited to the target
   month". The README, `docs/frozen_rules.md` §1 and the code search the month **plus the 10 days before it** (for
   announcements). A judge comparing the two will spot it. Fix: "limited to the target month and the 10 days before
   it, because price changes are often announced early; an event counts only if it takes effect inside the month."
3. **Devpost mixes two event counts in one section.** "4 of 9 replay events" (confirmed by 2 sources) sits next to
   "5 of 12 replay events found a confirming result" (evidence chase). The 12 includes the 3 wrong rows removed by
   Amendment 3, and the report card has the same mix. Fix: "5 of the 12 events found before the bug fixes", or
   recount the chase on the 9.
4. **FAQ Q1 still overstates the gain.** "The gain over trend is real but modest": the gain is 0.212 → 0.194 points
   over 9 months, and `docs/honest_limits.md` says differences this small "may be luck". Fix: "The gain over trend is
   small (0.21 → 0.19 points) and, with 9 months, may be luck. We report it next to the trend baseline rather than
   claiming a win."
5. **The README uses "call" for two different things.** "seals each call in public" means a prediction, but the
   tables just below say "Calls sent: 622 / 719" for API calls. The Devpost and video also say "the October call".
   Fix: say **"estimate"** for the prediction everywhere, and keep "call" for API calls only.

**Before submitting:** merge PR #8. Until then, `docs/honest_limits.md` on main still says the quote check covered
"only one row", and the audit file lacks the quote-check columns.

## 1. Number check

✓ = matches the source. ✗ = does not match. "n/c" = can't be checked from repo files.

### README.md

| Number in text | Source | Match | Note |
|---|---|---|---|
| 0.194 average miss; 0.150 vs poll 0.148 on 6 months | `score_lock.json` (`mae.c` 0.1937; poll months c 0.1497, poll 0.1483) | ✓ | |
| Audit 5 / 3 / 3 / 1; 9 with a second source | `audit/event_audit.md`, `results/app/audit_summary.json` | ✓ | |
| Recall 9 of 29; 14 with official series | `audit/missed_events.md`, `audit_summary.json` | ✓ | |
| Nano 622 calls, Super 719, Ultra 0 | `results/app/flight_recorder.jsonl` (uncached, by model): 622 / 719; Ultra only in `config/models.json` | ✓ | 622 + 719 = 1,341 |
| Model IDs | `config/models.json` | ✓ | |
| `nemotron.py` L69 (POST), L78 (fallback); `settings.py` L8 (base URL) | code at `9345bdc` | ✓ | |
| `tavily.py` L26 (all requests), L70 (`/usage`); `live_run.py` L68 | code at `9345bdc` | ✓ | |
| `evidence.py` L258 (Search), L280 (Extract), L522 (IBJA Extract) | code at `9345bdc` | ✓ | |
| `prompt_t.py` L65 (Map), L316 (chase Search) | code at `9345bdc` | ✓ | |
| Live runs refused below 150 credits left | `config/budget.json` `usage_floor` 150 | ✓ | There is also a `credit_floor` of 100 on the ledger balance; "or below 100 on our own ledger" would be complete |
| "plus 10 days before" | `docs/frozen_rules.md` §1 | ✓ | Conflicts with FAQ Q3 (top issue 2) |
| 788 Tavily calls; 694 of 1,500 credits; 77% inside the window | `results/tavily_report_card.md` | ✓ | |
| 5 official sites; 6 dairy sites | report card: 5 official; dairy table has 7 rows (Sanchi listed twice: MPCDF and Indore union) | ✓ | Fine if Sanchi counts once |
| 5 of 9 inside range; 14–21% measured | `score_lock.json`; `replay.csv` 0.141–0.209 | ✓ | |

### docs/devpost_draft.md

| Number in text | Source | Match | Note |
|---|---|---|---|
| 6.0% (RBI, Oct–Dec 2026) | `audit/dates_check.md` | ✓ | |
| 5 of 9; ± 0.28 (80th percentile of \|miss\|) | `score_lock.json`; `after_scoring_changes.md` ± 0.284 | ✓ | |
| 14–21%; 11% from the spine | `replay.csv` | ✓ | |
| Skeptic widened in 1 of 9 months (January) | `replay.csv` note on 2026-01 | ✓ | |
| Table: (a) 0.212 / 8; (b) 0.225 / 9; (c) 0.194 (0.185) / 7 (8); B1 0.468 / 0; poll 0.148 / 6 of 6; (c) 0.150 (0.138) | `score_lock.json`, `scoreboard.md` | ✓ | |
| (c) vs (b): −0.031, better in 6 of 9 | `tavily_attribution.csv` | ✓ | |
| 12 → 9 events | `after_scoring_changes.md` §4 | ✓ | |
| November seal by 3 Dec; release expected 14 Dec | handover plan; `audit/dates_check.md` | ✓ | "What's next" says "seal November before its release"; say "by 3 Dec" there too |
| 788 calls; 694 / 1,500; 40.3 credits per prediction; 77% (1,952 of 2,535) | report card | ✓ | |
| 91 of 93 quotes verified | report card | ✓ | |
| 4 of 9 confirmed by 2 sources; 5 of 12 chase matches | report card | ✓ but mixed bases | Top issue 3 |
| 4.3 s median; 154 direct calls | report card; flight recorder (4.29 s; 154) | ✓ | |
| 622 / 719 / 1,341 Nemotron calls, median 1.6 s | flight recorder (1.56 s) | ✓ | |
| 2,860 markets | external (MoSPI 2024 series: 1,465 rural + 1,395 urban) | ✓ | Add a source link |
| Step 3: "other replay months skipped web quotes" | `docs/frozen_rules.md` §5: replay months quote **only LPG and petrol** | partly | Say "other replay months quoted only LPG and petrol prices, to save credits" |

### docs/video_script.md

| Number in text | Source | Match | Note |
|---|---|---|---|
| 12 Nov, 4:00 PM IST | `audit/dates_check.md` | ✓ | |
| J&K +6.83% from 1 Sep | `manifests/2026-09.json` (event applied) | ✓ | |
| 14–21% measured | `replay.csv` | ✓ | |
| 0.194; 0.150 vs 0.148; 5 of 9 | `score_lock.json` | ✓ | Fair comparison now |
| January 0.17 points too low; 3 contrary quotes; landed inside | `replay.csv` (2.568 vs 2.74; note; inside True) | ✓ | But see top issue 1 |
| Audit 5 / 3 / 3 / 1; 0.185 → 0.194 | `audit_summary.json`, `score_lock.json` | ✓ | |
| 117 Tavily calls for March | `results/app/tavily_trace_2026-03.json` `n_calls` 117 | ✓ | It also cost 110 credits; worth saying |
| Length 2:45 | voice-over is 378 words = 2:42 at 140 wpm | ✓ | |

### drafts/judge_faq.md

| Number in text | Source | Match | Note |
|---|---|---|---|
| Nano cutoffs: pre-training 25 Jun 2025, post-training 28 Nov 2025 | NVIDIA model card (Hugging Face) | n/c | Hugging Face is blocked here |
| Super cutoffs: pre-training Jun 2025, post-training Feb 2026 | NVIDIA API docs and Docker Hub say Feb 2026; one university mirror says **Mar 2026** | ✓ (likely) | If March is right, the overlap covers Jan–**Mar** test months. Say "February 2026 (one mirror says March)" or re-check the card. |
| Recall on 2025: 3 of 4 | `docs/frozen_rules.md` §9, `after_scoring_changes.md` §4 | ✓ | |
| 0.185 → 0.194; 9 / 29 / 14; 0.150 vs 0.148; poll 6 of 6 | `score_lock.json`, `audit/*` | ✓ | |
| 622 / 719; 14–21%; 5 of 9 | flight recorder, `replay.csv`, `score_lock.json` | ✓ | |

### docs/honest_limits.md (with PR #8)

| Number in text | Source | Match | Note |
|---|---|---|---|
| 0.148 / 0.150 / 0.138; 0.194 / 0.185; 0.21; 0.47; 0.225 vs 0.212 | `score_lock.json` | ✓ | |
| 14–21%; 5 of 9; ± 0.28; under-predicted in 7 of 9 | `replay.csv`, `after_scoring_changes.md` | ✓ | |
| Quote check: 9 visible quotes verbatim, 1 paywalled, 2 unreachable, 3 dates later | `audit/event_audit.md` (PR #6, inside PR #8) | ✓ | |
| Recall 9 of 29; 14 of 29 | `audit/missed_events.md` | ✓ | |
| Gujarat about 7% of milk spending | MoSPI state weights | n/c | |

## 2. Contradictions between the files

| # | Says | But | Fix |
|---|---|---|---|
| 1 | FAQ Q3: searches "limited to the target month" | README and `frozen_rules.md` §1: the month plus the 10 days before it | Top issue 2 |
| 2 | Devpost: "4 of 9" events with 2 sources | same section: "5 of 12" chase matches | Top issue 3 |
| 3 | Replay page and video: "One miss explained: January" | January was inside the range; February was the biggest miss (0.38, outside) | Top issue 1 |
| 4 | Devpost step 3: other replay months "skipped web quotes" | `frozen_rules.md` §5 and `config/budget.json` cut 2: replay months quote LPG and petrol only | Reword (§1) |
| 5 | Devpost "Sealed calls": November sealed "by 3 Dec" | Devpost "What's next": "seal November before its release (likely Mon 14 Dec)" | Use "by 3 Dec" in both |
| 6 | Video scene 4: "official gold, gas and petrol price lists" | IBJA is the bullion and jewellers' association, not a government body | "published gold rates and the official gas and petrol price lists" |
| 7 | `docs/honest_limits.md` on main: quote check "for only one row" | PR #6 / #8: 9 of 12 checked by hand | Merge PR #8 |

No contradictions remain on the headline numbers: 0.194, 0.150 vs 0.148, 5 of 9, ± 0.28, 14–21%, the audit and the
recall figures agree in every file.

## 3. Jargon a judge won't understand

| Term | Where | Plain-English replacement |
|---|---|---|
| nowcast / experimental nowcast | Devpost one-liner, video | "an estimate of this month's figure, made before it is published" (keep "experimental" once) |
| call (meaning a prediction) | README, Devpost, video | "estimate" (keep "call" for API calls) |
| percentage points / pp | all | Explain once: "points of inflation, so 4.8% vs 5.0% is 0.2 points" |
| spine / government price spine | Devpost, honest_limits | "the government's daily retail food prices" |
| carried on trend | all | "assumed to keep moving as it has in recent months" |
| carve-out / "moves only its own share of the basket" | README diagram, video | "each measured item counts only in proportion to how much households spend on it" |
| combine index LEVELS, year-on-year last | README diagram, Devpost step 7 | "add up the official index values with official spending weights, then compare with a year ago" |
| (a), (b), (c), B1 | Devpost table, FAQ | "trend only", "government food prices only", "Shadow CPI", "repeat last month" (the app already uses plain labels) |
| leave-one-out, out-of-sample | Devpost | "each month's range was built from our misses in the other 8 months" |
| 80th percentile of the misses ignoring their sign | Devpost | "wide enough to cover 7 of our 9 test misses" (7.2 of 9 is the 80th percentile, so 7 is the plain count) |
| canonical JSON, SHA-256, git tag | README, Devpost, video | "a fingerprint of the file, published before the release; any later change would show" |
| flight recorder, cached, credits | all | "a log of every outside request, what it cost and how long it took"; "re-used at no cost"; "Tavily usage units" |
| gatekeeper | README, FAQ | "a small model that only answers yes or no: does this page state an Indian price?" |
| query-focused chunks, `include_domains_mode="prefer"` | Devpost "Why Tavily" | fine for the Tavily judges; add plain words once: "only the passages about prices", "prefer Indian news sites without blocking others" |
| PSU | README, Devpost | "state-owned companies" |
| leak guard | README diagram, FAQ | "a filter that drops any page that already states the official figure" |
| MoSPI, DoCA, IBJA, IOCL, PPAC | all | Spell out once: MoSPI (the statistics ministry), DoCA (Department of Consumer Affairs), IBJA (India Bullion and Jewellers Association), IOCL (Indian Oil), PPAC (the oil ministry's price cell) |

## 4. Claims that overstate the results

| # | Claim | Where | Why it overstates | Safer wording |
|---|---|---|---|---|
| 1 | "The gain over trend is real but modest" | FAQ Q1 | 9 months; honest_limits says it may be luck | Top issue 4 |
| 2 | "with every number cited" | README headline | 79–86% of the basket follows MoSPI's own trend. That is cited to MoSPI, but a judge may read it as "every price" | "with a source for every measured price" |
| 3 | "Tavily evidence lowered the mean miss from 0.225 to 0.194 pp" | Devpost "Attribution" | True; no sample caveat beside it | Add "over 9 months, a small difference that could be luck" |
| 4 | "Does it work?" followed only by averages | video scene 8 | Fine as worded now ("about a tie"); keep the range line | No change; don't add "accurate" in the edit |
| 5 | "One miss explained" on a month that landed inside the range | app, video scene 9 | Looks like the flattering pick | Top issue 1 |
| 6 | "official gold … price lists" | video scene 4 | IBJA is not official | Contradictions #6 |
| 7 | Handover pitch "for about ₹35 a prediction" | not in any doc (good) | No results file turns 40.3 credits into rupees, and Nebius costs aren't counted | Keep it out unless a results file computes it |

The sweep found no "beats the economists", "accurate", "outperforms" or "highly" anywhere.

## 5. The first 5 sentences a judge reads

1. **README headline**
   - Now: "Shadow CPI predicts India's official CPI inflation before it's published, from live web evidence, with
     every number cited, and seals each call in public before release."
   - Clearer: "Shadow CPI estimates India's official inflation rate before the government publishes it, using dated
     price evidence from the web. It cites a source for every measured price and locks each estimate in public
     before the release."
2. **README result line**
   - Now: "Jan–Sep 2026 replay: Shadow CPI missed by 0.194 percentage points on average; on the 6 months with an
     economists' poll, 0.150 vs the poll's 0.148 (about a tie)."
   - Clearer: "Tested on January–September 2026 with rules fixed in advance, Shadow CPI was off by 0.19 percentage
     points on average. On the 6 months with an economists' poll, it tied with the economists (0.150 vs 0.148)."
3. **Devpost one-liner**
   - Now: "An experimental, sealed nowcast of India's next official CPI inflation number. It is made before MoSPI
     releases the number, has a source behind every measured price, is locked in public, and is scored when the real
     number comes out."
   - Clearer: "An experimental estimate of India's next official inflation figure, made from dated web evidence
     before the government publishes it, locked in public, and scored against the real number when it comes out."
4. **Devpost "What it does", first bullet**
   - Now: "Shows an **experimental nowcast** of the coming month's CPI inflation (year-on-year), with an 80% range
     and the chance that the headline is 6.0% or more (the RBI's projection for Oct–Dec 2026)."
   - Clearer: "Shows our estimate of this month's inflation rate (compared with a year ago), a range we expect the
     real figure to fall in about 8 times out of 10, and the chance it reaches 6.0%, the Reserve Bank of India's
     projection for October–December."
5. **Video opening (scene 1)**
   - Now: "This is our experimental nowcast of India's October inflation. It's sealed and waiting. On the twelfth of
     November the government publishes the real number, and then everyone can see how close we got."
   - Clearer: "This is our estimate of India's October inflation, made before the official figure. It's locked: we
     can't change it. On the twelfth of November the government publishes the real number, and everyone can see how
     close we got."
