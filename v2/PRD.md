# Shadow CPI v2: PRD and build board

Oct 21, 2026 · @Shweta Jain

## Problem

India's official CPI for a month arrives around the 12th of the next month; October 2026's lands on Thu 12 Nov, 4:00 PM IST. Until then journalists, economists and businesses work from guesses, and the usual benchmark is an economists' poll.

Shadow CPI v1 already shows that a web-evidence nowcast can keep pace with that poll. Over Jan to Sep 2026 it missed by 0.194 percentage points on average, and by 0.150 against the poll's 0.148 on the six polled months.

What v1 does not yet show:

- **How much Tavily adds.** Only 21% of September's basket was measured from evidence; 79% was carried on trend.
- **Recall.** 9 of 29 known retail price changes were found directly (14 of 29 with official series).
- **The process.** Visitors see a finished number, not how it was built.
- **Live proof.** The October call seals on 29 Oct and is scored only after release.

v2's job: make Tavily's contribution visible, larger and measured, without weakening the pre-registered honesty that is v1's main asset.

## Solution

v2 lets people watch India's inflation number form, quote by quote, and then watch it get scored against the official release. Three moments carry the demo:

1. **Live build.** One button sends agents across the CPI basket, in Indian languages and regions. Evidence cards stream in, each marked verified or rejected with a reason. A treemap of the basket fills in by weight, and the CPI needle moves with each verified quote.
2. **Time machine.** A slider moves through the month and shows only evidence published by that date, and the nowcast line moves toward the official number. It is labelled a retrospective replay, because today's pages are not archived copies of what readers saw then.
3. **Proof.** The October call is sealed on 29 Oct with a public, timestamped record of the forecast and everything behind it. The video shows that commitment; the score arrives with MoSPI's release on 12 Nov, before judging opens on 1 Dec, and the app shows it beside the call.

Two supporting pieces turn the demo into a product and a contribution:

- **Price Shock Radar.** A daily feed of verified price changes, each converted into its effect on headline CPI in percentage points, with the quote attached.
- **Time-locked replay harness.** An open-source module anyone can use to backtest a search agent on the web as it was on a given date, without leakage from later pages.

## User stories

Three readers matter: a journalist who writes the CPI story, an economist who checks the method, and a hackathon judge with three minutes.

**Journalist**

1. As a journalist, I want this month's nowcast with its range and coverage, so that I can report it without overstating it.
2. As a journalist, I want every number to link to a dated quote on its source page, so that I can check it before I print it.
3. As a journalist, I want a daily feed of price changes with their effect on headline CPI, so that I can spot the story before the release.
4. As a journalist reading in English, I want an English gloss under every non-English quote, so that I can use regional evidence.

**Economist**

5. As an economist, I want the scoreboard against simple baselines and the poll, so that I can judge whether the method adds anything.
6. As an economist, I want to see the nowcast with and without web evidence, so that I can see what search contributes.
7. As an economist, I want the time machine to use only evidence dated before each cutoff, so that the backtest has no look-ahead.
8. As an economist, I want rejected evidence shown with its reason, so that I can see the filter is working.

**Judge**

9. As a judge, I want to press one button and watch the number form from live Tavily and Nemotron calls, so that I can confirm the app really runs.
10. As a judge, I want to see the sealed October call scored against the official figure, so that I can trust the claims.
11. As a judge, I want a log of every outside call with credits used, so that I can see the engineering is careful.

## Tavily design

Each Tavily capability gets one real job, and nothing reaches the index until Extract has confirmed the quote on its page. The rule is **search proposes, extract verifies**.

| Capability | Job in Shadow CPI | Key settings | Measured by |
| --- | --- | --- | --- |
| Search | Find price-change events in English, Hindi and regional-language press | start\_date / end\_date locked to the cutoff; news topic; one query set per language | Recall on the 29 known changes |
| Extract | Confirm each quote word for word on its page; read official price tables | focused query per item; a few chunks per source | Share of proposals verified vs rejected |
| Map | Discover new documents each month on official sites (regulators, dairy co-ops, oil companies) | limited depth, site list chosen from where v1 missed changes | New documents found per month |
| Crawl | Monthly sweep of those sites for orders effective that month | instructions name the month and item | Changes found that no search returned |
| Research | A "what did we miss?" sweep that only proposes candidates | output goes straight to the verify step | Verified changes added by the sweep |

&#91;embedded content: evidence pipeline · propose, read, verify, index\]

Tavily proposes candidates, Nemotron Nano reads the price, and Extract checks the quote and its date on the page; rejected items stay visible with their reason.

Every call goes through one cached client that writes to the Flight Recorder, so credits and cache hits stay visible.

**Time-locked replay.** Search date filters select pages by publication date; they do not show a page as it looked on that date, and a page can be updated while keeping its old date. So every fetched page's text is now saved and hashed when it is fetched, the verifier rejects quotes whose page shows a date after the cutoff, and the audit page counts those rejections. Jan to Sep are reported as a retrospective replay; the sealed live calls are the prospective test.

**Where announcements are published.** Candidate list from a Perplexity search on 21 Oct; each site still needs checking before it goes into the crawl list.

| Category | Primary source with dated announcements | Tavily job |
| --- | --- | --- |
| CNG and piped gas, Delhi-NCR | IGL current price table with effective dates; IGL CNG price chronology workbook | Map and Crawl; Extract the table |
| Medicine ceiling prices | NPPA ceiling price list | Map and Crawl |
| GST rate changes | CBIC GST notifications | Map and Crawl |
| Electricity tariffs | State regulators' tariff orders: DERC, UPERC, KERC/BESCOM, CSERC first | Map and Crawl; Extract the order |
| Milk, Mother Dairy | Mother Dairy press releases | Map and Crawl |
| Essential food prices | Department of Consumer Affairs daily price monitoring | Extract, as in v1 |
| Milk co-ops (Amul, Nandini, Aavin, Verka), LPG, CNG outside Delhi, bus, metro and rail fares, mobile tariffs | No dated primary archive found | Search in English and regional languages, then Extract to verify |

The last row is where Tavily Search matters most: those changes appear in the press, often in regional languages, and nowhere else.

## Nemotron and Nebius design

Each Nemotron model does the job its size suits, all served through Nebius Token Factory; the daily radar runs as a Nebius Serverless Job.

| Part | Job | Why this choice |
| --- | --- | --- |
| Nemotron Nano (v1 uses NVIDIA-Nemotron-3-Nano-30B-A3B) | Pull quoted, dated prices from pages; translate regional quotes into an English gloss | High volume, fast, cheap; v1 already made 10,006 calls |
| Nemotron Ultra | Referee conflicting evidence for the same item and month, with a written reason | Few calls that need careful reasoning; matches the track's own advice |
| Plain code | Turn verified price changes into the CPI estimate and range | The number is computed, never generated |
| Nebius Token Factory | Every model call at runtime | Required by the rules; shown live in the demo |
| Nebius Serverless Jobs | Run the Price Shock Radar every day, and the month-end sweep | Encouraged in the track; makes the radar run without a person |

The README and video must say where Token Factory sped the work up, and the submission form asks for feedback on Token Factory and the NVIDIA models.

## Implementation decisions

v2 is built as five deep modules, each with a small interface and its own tests, so an AI coding agent can change the inside of one without breaking the others.

| Module | Interface (in, out) | Notes |
| --- | --- | --- |
| Evidence finder | month, cutoff date → candidate quotes with URL | Search, Map, Crawl and Research behind one call; all through the cached Tavily client |
| Verifier | candidate → verified or rejected, with reason | Extract checks the exact line and the page date; Ultra referees conflicts |
| Evidence ledger | verified records → query by month, item, date | Stores published date, effective date and found date; the time machine needs all three |
| Index engine | ledger + weights → nowcast, 80% range, coverage | v1's plain-code method, unchanged unless v2 is scored |
| Replay harness | method + cutoff → score | Time-locked; published as its own open-source package |

Decisions:

- No quote reaches the index without a verified exact line and a page date on or before the cutoff.
- Every non-English quote carries an English gloss, because the rules require English materials.
- The "Run live" button is rate-limited and served from cache where possible, so judges cannot drain the Tavily budget.
- The live build view streams results as they arrive instead of waiting for the full run.
- v1's code and results stay frozen in their own folder; v2 sits beside it.

Added after the 21 Oct review:

- Each ledger record also stores place, unit, price type (household retail, wholesale or commercial) and the CPI item it maps to. Only household retail prices that map to a CPI item enter the headline; the rest are shown as context. The 19 kg commercial LPG cylinder, for example, is not the household LPG item.
- The seal is a public, timestamped hash of the forecast plus its evidence manifest (saved page text), model IDs, weights, config and code commit, with a page that lets anyone check it.
- "What moved" drivers are computed in code as weight times price change; the model only writes the words around computed numbers.

## Testing and scoring

v1's scoreboard stays frozen as published; v2 gets its own rule, written down before it is run, and is scored once.

**Cutoff rule.** The replay uses the same cutoff as the live call: evidence published up to the 29th of the reference month. v1's replay windows ran to the month's last day (September's to 30 Sep), so v2 fixes this.

**Development and test months.** v1's rules were set after looking at Jan to Sep, so those months are development data. The sealed calls from October on are the real test. ~~The poll baseline uses only polls published before the same cutoff.~~ Removed by Amendment D: polls come out about 10 days after our 29th cutoff, so the unfiltered poll has more information and is the tougher benchmark.

**Range check.** The September example brief shows 5.80% with an 80% range of 5.78% to 6.14%; MoSPI published 5.54% on 12 Oct ([DD News](https://ddindia.co.in/2026/10/retail-inflation-rises-to-5-54-in-september/)), below the range. Every brief shows the official figure beside the call once it is out.

**v2's pre-registered rule** (fill in and commit before the first v2 run):

- [x] Pass if v2 beats "repeat last month" and "trend only" on Jan to Sep 2026, same as v1's rule.
- [x] Report v2 beside v1 whatever the result, including if v2 is worse.
- [x] Commit the rule with a timestamp before scoring (`v2/PREREGISTRATION.md`, 2026-10-22, with Amendments A–D).

**Measures reported for v2:**

| Measure | v1 today | v2 target |
| --- | --- | --- |
| Average miss, Jan to Sep (pp) | 0.194 | Set before scoring |
| Recall on the 29 known changes (found directly) | 9 of 29 | Set before scoring |
| Basket share measured from evidence (Sep) | 21% | Set before scoring |
| Actual inside 80% range | 5 of 9 months | Set before scoring |
| Lift from web evidence (with vs without) | Not shown | Shown on the home page |
| Quotes rejected for a page date after the cutoff | Not shown | Shown on the audit page |

**Code tests:**

- Index engine: known inputs give known outputs.
- Verifier: a saved set of pages with true and false quotes, including one edited after its date.
- Replay harness: no record dated after the cutoff can enter a replay.
- Live run: one end-to-end run against the deployed app before each daily push.

## Out of scope

These stay out of v2 so the nine days go to the demo and the Tavily story.

- State-level CPI nowcasts.
- Other countries or other official statistics.
- Forecasts beyond the current month.
- Paid data sources or scraping outside Tavily.
- Re-tuning or re-scoring v1.
- A separate mobile app; the Streamlit site must simply work on a phone.
- User accounts, alerts by email, or a paid tier.

Also cut after the 21 Oct review:

- A state heatmap presented as a CPI view. A map may show where quotes came from, labelled as such.
- Agent or call counts as a headline. The Flight Recorder stays as an audit page.
- AI-written explanations of what moved, unless the numbers come from code.

## Issue board

17 issues, each a vertical slice that ends in something a judge can see; issue 1 is the tracer bullet the rest build on. AFK means an AI coding agent can do it from the issue text alone; Human means it needs your decision.

| # | Slice | What a judge sees | Blocked by | Mode | Days | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | One basket item end to end: find, verify, ledger, streamed onto a new Live build page | A card appears, turns green, the needle moves | None | AFK | Oct 22 | Done (2026-10-22) |
| 2 | Live build for the whole basket: treemap by weight, rejected cards with reasons | The basket fills in live | 1 | AFK | Oct 22–23 | Done |
| 3 | Time machine slider and convergence chart from ledger dates, labelled a retrospective replay | The line converges on the official number | 1 | AFK | Oct 23–24 | Done |
| 4 | Regional-language search through the verify step; rerun the recall check | Recall above 9 of 29 | 1 | AFK | Oct 23–25 | In progress (recall run under Amendment C) |
| 5 | Check the Perplexity site list; Map and Crawl the sites with dated archives monthly | Changes no search returned | 1 | Human | Oct 24–25 | **Cut** (Amendment D) |
| 6 | Research "what did we miss?" sweep, proposals only | Extra verified changes | 1 | AFK | Oct 25 | **Cut** (Amendment D) |
| 7 | Ultra referee for conflicting evidence | A conflict settled with a reason | 4 | AFK | Oct 25–26 | **Cut** (Amendment D) |
| 8 | "What Tavily adds" panel: with vs without web evidence | Tavily's lift at a glance | 1 | AFK | Oct 24 | Done |
| 9 | Price Shock Radar page, effect on headline in pp | A daily story feed | 1 | AFK | Oct 25–26 | Not started |
| 10 | Run the radar daily as a Nebius Serverless Job | It runs with no one there | 9 | AFK | Oct 26–27 | Not started |
| 11 | English gloss under every non-English quote | Regional evidence readable in English | 1 | AFK | Oct 24 | Done |
| 12 | Reliability: rate-limit Run live, reserve credits, check the Streamlit wake-up | Demo works until 15 Dec | None | AFK | Oct 27 | Mostly done in v1 (rate limit, reserve, wake-up job) |
| 13 | Package the time-locked replay harness as open source | A reusable contribution | 3 | AFK | Oct 26–27 | Not started |
| 14 | Commit v2's rule, score v2 once, show it beside v1 | An honest v1 vs v2 table | 4, 5, 6, 7 | Human | Oct 27–28 | Next (rules committed: Amendments A–D) |
| 15 | Decide v1 or v2 for October; seal the call | A sealed call before the deadline | 14 | Human | Oct 29 | Not started |
| 16 | Public timestamped seal (forecast, saved page text, model IDs, code commit); ask organizers, then build auto-scoring from the MoSPI release | The app grades itself in December | 15 | Human | Oct 22 ask, Oct 28 build | Not started |
| 17 | Submission: one consistent story across app, README, Devpost text and 3-minute video; feedback | A complete entry | 2, 3, 8, 15 | Human | Oct 29–30 | Not started |

If time runs short, cut in this order: 13, 10, 7, 6, 9. Issues 1, 2, 3, 8, 11, 12, 15 and 17 are the floor.

## Schedule and submission

Code freezes on 28 Oct, the call seals on 29 Oct, and the entry goes in on 30 Oct by 10:30 PM IST. MoSPI's release on 12 Nov lands before judging opens on 1 Dec.

&#91;embedded content: v2 schedule · build to judging\]

Winners are announced around 11 Jan 2027.

**Submission checklist** (from the official rules):

- [ ] Public repo with an open source license visible at the top of the repo page
- [ ] README with setup steps, how Nemotron and Token Factory are used, and a Tavily section
- [ ] Devpost description: what it is, why, how it works; track Best Apps and Agents (recommended)
- [ ] Demo URL that works without a login and keeps working until 15 Dec
- [ ] Public YouTube video under 3 minutes showing Token Factory, Nemotron and Tavily at work
- [ ] Everything in English, including glosses for non-English quotes
- [ ] Feedback on Token Factory and the NVIDIA models filled in
- [ ] If any part existed before 26 Aug, a note on what changed during the submission period
- [ ] Draft saved on Devpost by 28 Oct; final submission before 30 Oct, 10:30 PM IST

## Risks and open questions

The biggest risk is scope: if the build slips, the cut order on the issue board protects the floor.

| Risk | Fallback |
| --- | --- |
| v2 scores worse than v1 | Seal October with v1; show v2 as experimental, beside v1, honestly |
| Tavily or Token Factory credits run out before 15 Dec | Cache everything; reserve a fixed budget for Run live; rate-limit it |
| A page was edited after its date and leaks the answer | Save and hash page text at fetch time; reject quotes whose page date is after the cutoff; call Jan to Sep a retrospective replay |
| Regional-language extraction makes mistakes | Every non-English quote is verified on its page and glossed; the referee settles conflicts |
| Organizers treat auto-scoring as a change after the deadline | Ask in writing now; if refused, show the sealed call and let judges compare it with MoSPI themselves |
| Streamlit's free hosting sleeps when idle | Test the wake-up; mention it in the testing notes |
| The video is recorded before 12 Nov, so it cannot show October's score | Show a finished replay month with its cutoff and error, then the sealed commitment; the score appears in the app later |
| Project materials contradict each other (older drafts mention 300 agents, a Jul to Sep replay, six weeks' notice) | One consistency pass across app, README, Devpost text and video; CPI arrives about 12 days after month end, so a 29th seal gives about 14 days' lead |

Open questions:

- [ ] Which Token Factory model IDs to use for Nemotron Super and Ultra?
- [ ] How many Tavily and Token Factory credits are left?
- [ ] Which of Perplexity's candidate sites hold the 20 changes v1 did not find directly?
- [ ] Does saved v1 evidence already store published and effective dates?
- [ ] Does the October call go out from v1 or v2?
- [ ] Did any part of Shadow CPI exist before 26 Aug?

## Sources

- [Hackathon overview](https://nebiusglobalaihackathon.devpost.com/)
- [Official rules](https://nebiusglobalaihackathon.devpost.com/rules)
- [Tavily documentation](https://docs.tavily.com/)
- [Shadow CPI v1 app](https://shadow-cpi.streamlit.app/), read 21 Oct 2026


## Changes since this PRD (2026-10-22)

Recorded in `v2/PREREGISTRATION.md` (Amendments A–D, each committed with a timestamp before scoring).

**Deviations from the PRD**
- **Nemotron Super** (`nvidia/nemotron-3-super-120b-a12b`) re-reads a page when Nano cites a line with no number
  (Amendment B). The PRD lists only Nano (reading) and Ultra (refereeing); Ultra is not used, because issue 7 is cut.
- **Full-page Extract** for verification, instead of "focused query per item, a few chunks": checking the exact
  cited line needs the whole page.
- **Poll baseline** stays unfiltered (see Testing and scoring).
- **Saved page text** is hashed at fetch time and kept locally, not committed (news articles); the ledger keeps
  each page's SHA-256.

**Decided before scoring (Amendment D):** v2's range is v1's live-month ± 0.284 pp; "v2 better than v1" needs a lower
mean miss and recall above 9 of 29; basket measured counts an event by its state's share (v1 recomputed the same
way); a quote is rejected if its page shows a date after the cutoff or more than 2 days after Tavily's published date;
wholesale and commercial prices are context only, with `price_type` in the ledger.

**Issues cut:** 5, 6 and 7.
