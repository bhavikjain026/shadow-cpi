# Shadow CPI v2: pre-registration

**Written 2026-10-22T03:21:54Z (UTC), before any v2 run.** No v2 search, extraction, prediction or score existed
when this file was committed; the commit that adds it is the timestamp of record.

v1 (everything outside `v2/`) stays frozen: its code, rules, results and scores do not change. v2 lives in `v2/`
and in its own app page. Every v2 Tavily call goes through the existing cached client (`shadow_cpi/tavily.py`) and
the Flight Recorder, under hard credit caps in `config/budget.json`.

## 1. Cutoff rule (the main change from v1)

- For a target month *m*, v2 uses only evidence **published up to 23:59 IST on the 29th of *m*** (or the month's
  last day if it is earlier; February 2026: the 28th). This matches a live seal; v1's replay windows ran to the
  month's last day.
- Searches are date-locked: from 10 days before *m* starts (announcements) to the cutoff.
- Code checks each page's published date (page address first, then Tavily's published date). A page with no
  date, or a date after the cutoff, is not used.
- Each page is saved and its text hashed (SHA-256) at fetch time. The evidence ledger records the published date,
  the effective date, the date we found it, the place, the unit, the price type and the CPI item.

## 2. Who does what

- Tavily Search proposes pages; NVIDIA Nemotron Nano reads the price from the proposed text and cites a line.
- Tavily Extract fetches the page; code verifies that the exact cited line is on the page, that the price is in
  that line, and that the page date is within the window. No model writes a quote or chooses a number.
- Code decides every number, as in v1: index levels combined with the official 2024-series weights, year-on-year
  last, tracked items moving only their own weight.

## 3. Data and scoring

- **January–September 2026 are development data** for v2. v2 is built and debugged on them, so v2's Jan–Sep scores
  are in-sample and are labelled as such. They are not a clean test.
- **Pass rule (decided now):** v2 passes if its mean absolute miss over Jan–Sep 2026 is below both
  "repeat last month" (B1) and "trend only" (B2 = v1 model (a)), against MoSPI's published year-on-year figures.
- **Reported beside v1 whatever the result**, with the same metric (mean absolute miss, direction hit-rate), and
  on the economists' poll months as well.
- **Scored once.** The scoring script writes `v2/score_lock.json` and refuses a second run; any later change is a
  logged bug fix with scores before and after, as in v1.

## 4. What will not happen

- No v1 file, rule or result is changed by v2 work.
- The cutoff, the pass rule and the metric are not changed after any v2 score is seen.
- A v2 result is never presented as v1's, or the other way round.
