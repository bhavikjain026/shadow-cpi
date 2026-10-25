# Finance look-ahead check: pre-registration

**Written 2026-10-22T17:56:24Z (UTC), committed before any code for it and before any search.** Decided by the owner.
**Exploratory**: it changes no scored verdict, v1, the v2 locks or the October seal. Reuses the date-test harness
(`v2/date_test.py`: Wayback CDX labels, Wilson and exact McNemar code).

## Question
For scheduled financial events whose outcome was unknown until the day, does a Tavily search with no dates return
pages that state the outcome when replaying the day before, and do `start_date`/`end_date` +
`filter_by_published_date` stop that?

## Event list (fixed now, before any search; checked on 2026-10-22)
Cutoff = the day before each event. Sources are the official calendars where found, else the company's filing as
quoted by the source named; each was checked on 2026-10-22 by web search (no Tavily call).

| ID | Event | Event date | Cutoff | Source |
|---|---|---|---|---|
| R1 | RBI MPC decision (FY26 cycle, 4–6 Feb) | 2026-02-06 | 2026-02-05 | RBI FY26 MPC schedule; outcome reports e.g. drishtiias.com (7 Feb 2026) |
| R2 | RBI MPC decision (6–8 Apr) | 2026-04-08 | 2026-04-07 | RBI 2026-27 MPC calendar, rbi.org.in/SCRIPTS/Annualpolicy.aspx |
| R3 | RBI MPC decision (3–5 Jun) | 2026-06-05 | 2026-06-04 | same calendar |
| R4 | RBI MPC decision (3–5 Aug) | 2026-08-05 | 2026-08-04 | same calendar |
| R5 | RBI MPC decision (5–7 Oct) | 2026-10-07 | 2026-10-06 | same calendar; `audit/dates_check.md` (c) |
| C1 | TCS Q1 FY27 results | 2026-07-09 | 2026-07-08 | board-meeting date as reported (sahi.com, multibagg.ai) |
| C2 | Reliance Industries Q1 FY27 results | 2026-07-17 | 2026-07-16 | RIL board-meeting disclosure as quoted (multibagg.ai, freepressjournal.in) |
| C3 | HDFC Bank Q1 FY27 results | 2026-07-18 | 2026-07-17 | HDFC Bank intimation as quoted (multibagg.ai) |
| C4 | ICICI Bank Q1 FY27 results | 2026-07-18 | 2026-07-17 | ICICI Bank exchange filing as quoted (freepressjournal.in) |
| C5 | Infosys Q1 FY27 results | 2026-07-23 | 2026-07-22 | as reported (upstox.com) |
| C6 | TCS Q2 FY27 results | 2026-10-08 | 2026-10-07 | TCS intimation, tcs.com …/announcement-date-board-meeting-financial-results-q2fy27.pdf |
| C7 | HDFC Bank Q2 FY27 results | 2026-10-17 | 2026-10-16 | HDFC Bank intimation of 22 Sep 2026 (Form 6-K; psuconnect.in) |
| C8 | ICICI Bank Q2 FY27 results | 2026-10-17 | 2026-10-16 | ICICI Bank intimation as quoted (niftytrader.in) |
| C9 | Infosys Q2 FY27 results (board meeting 22–23 Oct) | 2026-10-23 | 2026-10-22 | as reported (upstox.com); **runs only if the check starts on or after 2026-10-24**, otherwise reported "not run" |

**Left out, logged:** Reliance Industries Q2 FY27: no board-meeting date was confirmed by 2026-10-22 (only a
"not confirmed" preview); it is not added later. The list is final: nothing is added or removed after this commit
except C9 under its rule above.

## Queries (neutral templates, fixed now)
- RBI: `RBI monetary policy repo rate decision <Month> <Year>` (e.g. "… February 2026").
- Companies: `<Company> Q<n> FY27 quarterly results` with Company = TCS, Reliance Industries, HDFC Bank,
  ICICI Bank, Infosys.

## Arms (same query, run close together in a seeded random order per event, seed 20261022)
Common: `topic` news, `search_depth` basic, `max_results` 5, `include_published_date` true, no domains, no
language, no auto_parameters.
- **N (no dates):** no date fields, `filter_by_published_date` false.
- **D (dates + filter):** `start_date` = cutoff − 29 days, `end_date` = cutoff, `filter_by_published_date` true.

## Labels (per result; search title + snippet only, no Extract)
- **States the outcome:** RBI: the text names the repo rate and a decision word (unchanged, kept, held, hike(d),
  raise(d), cut, reduce(d)) with a percentage. Company: the text names the company, the quarter (Q<n> FY27, or the
  quarter ended 30 June / 30 September 2026, or "June quarter"/"September quarter" 2026) and a result figure
  (profit, revenue or income with a ₹/Rs/crore amount or a % change).
- **Leak (confirmed):** states the outcome **and** the Wayback Machine CDX API (logged direct download, as the date
  test) has no capture on or before the cutoff, its first capture is after it, and Tavily's or the address's date is
  after the cutoff.
- **Date flag:** states the outcome and a date signal (Tavily, address) is after the cutoff, without that Wayback
  evidence. Reported separately; never counted as a confirmed leak.
- **Valid evidence:** a result Wayback-confirmed on or before the cutoff whose text names the RBI / the company.

## Metrics (per arm, n = events run)
1. Confirmed-leak incidence: events with at least one confirmed leak, x of n, **Wilson 95%** interval.
2. Date flags: results and events.
3. **N vs D paired, exact McNemar** (two-sided) on confirmed-leak events.
4. **Valid evidence lost:** valid results found by either arm and not kept by this arm.
5. Undated results; credits; median latency (Tavily `response_time`).

## Output and cap
`results/finance_lookahead.json` and `.md`, run once (the result file refuses a second run). Cap
`finance-lookahead` **60** credits in `config/budget.json` (about 28 search credits expected); a cap stops it
cleanly and marks it incomplete.

## Amendment 1 (logged), written 2026-10-25T12:50:43Z (UTC), before any finance call

Decided by the owner. Changes the event list's sources and the labels only; queries, arms, metrics and the cap are
unchanged. Sources re-checked on 2026-10-25 (web search and direct page reads, no Tavily call).

**(a) Official source for every date.** An event stays only if its date is confirmed by an official source (RBI site,
company site, stock-exchange filing, or the company's own SEC filing). Dropped: Reliance Industries Q2 FY27 (no
board-meeting date confirmed; already left out). No other event is dropped under (a).

**(b) Only events that have happened.** Every event must be before the run day. C9 (Infosys Q2 FY27) took place on
2026-10-23 (Infosys's own filing, below), so its earlier rule ("runs only if the check starts on or after
2026-10-24") is now met on any run day from 2026-10-24; no event is dropped under (b).

**(c) Sources, official first; the secondary link is kept only as a backup.**

| ID | Event date | Official source | Backup (secondary) |
|---|---|---|---|
| R1 | 2026-02-06 | RBI, Monetary Policy Statement 2025-26 (6 Feb 2026): rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR20530D3EAF28B417497981BA800A7B3C0DCC.PDF | drishtiias.com |
| R2 | 2026-04-08 | RBI MPC resolution (6–8 Apr 2026): rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62514 | — |
| R3 | 2026-06-05 | RBI MPC resolution (3–5 Jun 2026): rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62863 | — |
| R4 | 2026-08-05 | RBI MPC resolution (3–5 Aug 2026): rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63287 | — |
| R5 | 2026-10-07 | RBI MPC resolution (5–7 Oct 2026): rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63742 | — |
| C1 | 2026-07-09 | TCS press release, Q1 FY 2027: tcs.com/who-we-are/newsroom/press-release/tcs-financial-results-q1-fy-2027 | sahi.com, multibagg.ai |
| C2 | 2026-07-17 | RIL media release, results for the quarter ended 30 Jun 2026: ril.com/sites/default/files/2026-07/Media_Release_Consolidated_and_Standalone_Unaudited_Financial_Results_for_the_quarter_ended_June_302026.pdf | multibagg.ai, freepressjournal.in |
| C3 | 2026-07-18 | HDFC Bank results release (Form 6-K exhibit): sec.gov/Archives/edgar/data/1144967/000119312526308398/d101962dex99.htm; HDFC Bank financial calendar (hdfcbank.com) | multibagg.ai |
| C4 | 2026-07-18 | ICICI Bank notice of the 18 Jul 2026 board meeting: icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2026/NSEBSE_14072026.pdf (**date confirmed; no outcome filing was found**) | freepressjournal.in |
| C5 | 2026-07-23 | Infosys Form 6-K exhibit, "taken on record by the Board … on July 23, 2026": sec.gov/Archives/edgar/data/0001067491/000106749126000038/exv99w06.htm | upstox.com |
| C6 | 2026-10-08 | TCS press release, Q2 FY 2027: tcs.com/who-we-are/newsroom/press-release/tcs-financial-results-q2-fy-2027; TCS board-meeting intimation (tcs.com) | angelone.in |
| C7 | 2026-10-17 | HDFC Bank financial calendar (hdfcbank.com/personal/about-us/corporate-governance/financial-calendar); BSE results filing bseindia.com/xml-data/corpfiling/AttachHis/f5d5fb37-aa66-401c-85d6-58ccd3982828.pdf | psuconnect.in |
| C8 | 2026-10-17 | ICICI Bank BSE filing, board meeting of 17 Oct 2026: bseindia.com/xml-data/corpfiling/AttachHis/6daa2579-7a4f-493a-8058-18d2e45402e4.pdf | niftytrader.in |
| C9 | 2026-10-23 | Infosys Form 6-K exhibit, "taken on record by the Board … on October 23, 2026": sec.gov/Archives/edgar/data/0001067491/000106749126000042/exv99w03.htm | upstox.com |

**(d) Final event count: 14** (5 RBI decisions, 9 company results), at least 12. With 14 events the Wilson 95%
interval is still wide (0 of 14 → 0–22%; 7 of 14 → 27–73%); this is a small check, not a precise estimate.

**(e) Labels, aligned with the date test.** Judging uses the search title and snippet only, so:
- **Confirmed leak:** states the outcome **and** Wayback-confirmed (no capture on or before the cutoff, first
  capture after it, and Tavily's or the address's date after the cutoff). Only these count in the leak metrics
  (metrics 1 and 3).
- **Snippet leak:** the title/snippet states the outcome and a date signal (Tavily, address) is after the cutoff,
  but Wayback does not confirm it. Reported separately (results and events per arm); never counted as a confirmed
  leak. This replaces the earlier "date flag" for results that state the outcome.
- **Date flag:** a date signal after the cutoff on a result that does not state the outcome, as in the date test.

**Amendment 1, addendum (logged 2026-10-25T12:52:02Z UTC, offline, before any finance call).** Decided by the owner: **C4 is kept**,
flagged "date from the board-meeting notice; no official outcome filing found". Every metric is reported **both
ways**: all 14 events, and 13 events without C4.
