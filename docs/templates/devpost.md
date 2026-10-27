# Shadow CPI: Devpost write-up

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily. Every number below is filled from the results files by
> `python tools/sync_doc_numbers.py`; edit `docs/templates/devpost.md`, not this file.

## Headline
The web rewrites history. Our agent catches it.

## Tagline
An AI agent that searches the past without cheating: it writes its own Tavily searches inside a time lock it cannot
move, verifies every quote on the page, and seals India's inflation forecast before the government publishes it.

## Short description
<!-- short:start -->
Shadow CPI is a Tavily-grounded nowcast of India's Consumer Price Index (CPI) inflation that tests, rather
than assumes, Tavily's date controls and measures what they cost. An AI agent writes Tavily searches inside a
time lock, verifies every quote on the page with Tavily Extract and NVIDIA Nemotron, lets code
compute the number, and seals the {{live_month}} nowcast with a SHA-256 hash and git tag before the Ministry
of Statistics (MoSPI) publishes on {{release_day}}. With no dates, {{dt_nodates}} of {{dt_cases}} cases leaked a
not-yet-published page ({{dt_nodates_retry}} after an archive retry); with dates and the filter, {{dt_dated}} of {{dt_cases}}. The
cost: the time-locked search missed {{e_missed}} of {{e_quotes}} known-good quotes. In a
{{replay_span}} replay it missed by {{mae_c}} percentage points on average, against {{mae_trend}} for trend-only; on
poll months, about a tie with economists ({{mae_poll_c}} vs {{mae_poll}}).
<!-- short:end -->

## Inspiration
India's CPI arrives about {{release_lag}} days after the month ends. Forecasting it from the web means replaying past
months, and a replay that reads a page published after its cutoff looks better than it could ever be live. El Lahib et
al. ({{lahib_year}}, arXiv {{lahib_arxiv}}) found that {{lahib_pct}} of Google-audited questions had at least one major
post-cutoff page, after {{lahib_queries}} queries and about {{lahib_urls}} URLs each; our {{dt_nodates}}/{{dt_cases}}
({{dt_nodates_retry}}/{{dt_cases}} after the archive retry) is per search task, so the rates are not directly comparable. So we built a nowcast that tests, rather than assumes,
Tavily's date controls and measures what they cost.

## Related work
{{related_work}}

## Time-locked search leakage
- **Date test** (pilot, pre-registered): no dates, {{dt_nodates}} of {{dt_cases}} cases leaked
  ({{dt_nodates_retry}} of {{dt_cases}} after a logged archive retry); `start_date`/`end_date` +
  `filter_by_published_date`, {{dt_dated}} of {{dt_cases}} ({{dt_dated_retry}} of {{dt_cases}} after the retry).
- **Finance check** (exploratory; Reserve Bank of India (RBI) decisions and company results): no dates, {{fin_nodates}} of {{fin_events}}
  on the initial pass, {{fin_nodates_retry}} of {{fin_events}} after the retry; with dates and the filter,
  {{fin_dated}} of {{fin_events}} events with a confirmed leak ({{fin_dated_retry}} of {{fin_events}} after the retry). {{sr_fin_dated_after}} of {{sr_fin_searches}} filtered searches returned a result dated after the cutoff; an independent
  reviewer found {{sr_fin_reviewer_leaks}} page whose current version leaks the outcome (AI-assisted second review).
- **Leaks at three levels.** Task, no dates (initial pass → after the logged archive retry): date test
  {{dt_nodates}} → {{dt_nodates_retry}} of {{dt_cases}}, finance {{fin_nodates}} → {{fin_nodates_retry}} of
  {{fin_events}}; with dates and the filter, {{dt_dated}} → {{dt_dated_retry}} of {{dt_cases}} and {{fin_dated}} →
  {{fin_dated_retry}} of {{fin_events}}. Call: one search per task and setting, so the same counts
  ({{dt_leak_calls_nodates}} of {{dt_calls_nodates}} and {{fin_leak_calls_nodates}} of {{fin_calls_nodates}} on the
  initial pass). Result (exploratory, counted after scoring, initial pass): {{lt_leaks}} of {{lt_results}}, all from
  searches with no date window.
- **Check P, full page** (exploratory): of {{p_pages}} pages that passed the date lock, {{p_later}} described a later
  event; most later dates were page furniture ({{p_furniture}} of {{p_flagged}} flagged pages: date bars, sidebars,
  related links).
- **The cost of strictness in valid evidence lost (date test):** the filter dropped {{dt_lost_filter}} of
  the date test's {{dt_valid_total}} pieces of valid evidence.
- **The cost of strictness in known-good quotes missed (check E, exploratory, `exact_match`):** of
  {{e_quotes}} verified quotes, the dated search re-found {{e_found}} and missed {{e_missed}}; filter misses, not back-dating ({{e_missed_later}} of {{e_missed}} have a later
  `published_date`).
- **Receipt:** credits and median latency per setting:

{{leakage_table}}

## Search filters by date; Extract reads the page as it is today
A page dated before the cutoff can be updated after it, and Extract returns the updated page. Example (AI-assisted
second review, post-hoc): `{{ex_row}}`, a {{ex_company}} results preview, cutoff {{ex_cutoff}}; Tavily dated it
{{ex_published}}, and the page was updated on {{ex_updated}} with a link to the actual result. {{sr_fin_dated_after}}
of {{sr_fin_searches}} filtered searches returned a result dated after the cutoff; an independent reviewer found
{{sr_fin_reviewer_leaks}} page whose current version leaks the outcome. What covers the gap, partly: our page-date
check (kept {{dt_results_pagecheck}} of {{dt_results_filter}} filtered results in the date test; date-test valid
evidence lost: {{dt_lost_pagecheck}} of {{dt_valid_total}} with it, {{dt_lost_filter}} with the filter alone); the drift monitor, which re-reads October radar
pages daily ({{drift_phrase}}); and Wayback Machine checks, with failed lookups retried and logged
({{dt_retry_urls}} in the date test, {{fin_retry_urls}} in the finance check; {{sr_unclear}} of {{sr_rows}} second-review rows stayed unclear, partly
from archive rate limits).

## Let the model program its filters, inside a time lock it cannot move
Building on Tavily's dynamic-filtering idea, we let Nemotron write the search fields and tested it on
{{known_changes}} known price changes: code templates (arm A) found {{arm_a_recall}}, Nemotron-written fields (arms B
and C) {{arm_b_recall}} and {{arm_c_recall}}, `auto_parameters` (arm T) {{arm_t_recall}}; exploratory arm H
(templates + model-chosen fields) {{arm_h_recall}}, and T+dates {{arm_td_recall}}. The model's fields were always
valid ({{bc_fields_valid}} of {{bc_fields}}; {{arm_h_fields_valid}} of {{arm_h_fields}} in arm H), but fixed
templates found more; the likely cause is source choice (arm H differed from A only in domains and language).
Observed in our test, `auto_parameters` with no dates assumed "now": {{auto_oct}} of {{auto_results}} results came from {{live_month}}.
So the model chooses the query, topic, domains and language; code owns the dates.

## How it works
1. **Tavily Search proposes** pages, every call with `start_date`/`end_date` (the later time-locked searches also send
   `filter_by_published_date`; v1's frozen search used the dates plus our page-date check); code re-checks each date.
2. **Tavily Extract verifies the quote:** Nemotron cites a numbered line, and code checks the number is in that exact
   line. A model never writes a quote.
3. **Plain code computes:** index levels combined with MoSPI's official weights; year-on-year last.
4. **The seal:** canonical JSON + `SHA-256` + a git tag, before the release.

**NVIDIA Nemotron on Nebius Token Factory:** Nemotron Nano (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) is the yes/no
gatekeeper and writes display-only English glosses ({{nano_sent}} calls sent; {{nano_total}} including cache hits).
Nemotron Super (`nvidia/nemotron-3-super-120b-a12b`) reads pages, cites lines, and writes the search fields in arms B,
C and H ({{super_sent}} calls sent; {{super_total}} including cache hits). Token Factory helped: JSON-schema output
worked on the opening call, and both sizes sit behind one OpenAI-compatible endpoint, so roles are a config change.

## What it does
- **The {{live_month}} nowcast.** {{seal_status}}. MoSPI publishes on {{release_day}} at {{release_hour}} IST.
  Anyone can recompute the seal's `SHA-256` from the file at tag `seal-2026-10` (`verify.md`).
- **Price Shock Radar** (exploratory, report only): announced price changes taking effect this month;
  {{radar_events}} verified so far, {{radar_corroborated}} corroborated.
- **Live build** with **Replay a saved run** (no API call, no credits).
- **Chain of custody** from any number to its quote, page, Tavily request ID, response hash and seal; **`as_of()`**
  shows what was known on a past day.

## Reuse
`shadow_cpi/pit` (`pit_search(query, cutoff)`) and the agent skill `skills/time-locked-search/SKILL.md`. **For
research teams:** designed for event studies and backtests that must not see the outcome early; research tool, not
investment advice.

## Scoreboard
{{replay_span}} replay, rules frozen before scoring (`results/score_lock.json`): Shadow CPI v1 {{mae_c}} pp mean miss,
trend only {{mae_trend}}, repeat-last-month {{mae_b1}}. On the {{poll_months}} poll months: {{mae_poll_c}} vs the
poll's {{mae_poll}}, about a tie. The {{range_level}} range held in {{inside}} of {{months}} months. v2 was not
better ({{mae_v2}}).

## What we found about Tavily (bug reports)
- `auto_parameters` did not follow time-locked intent (observed in our test): {{auto_oct}} of {{auto_results}} results from {{live_month}} on
  searches about past months.
- `published_date` can be later than the page's own date: {{pd_later}} of {{pd_pages}} distinct pages, consistent with
  Tavily's documented definition (published or last updated, beta). Suggestion: separate original-publication and
  last-modified fields.
- Suggestion: an as-of / crawl-date field for Extract, so time-locked users can tell if a page changed.
- Undated pages are dropped by the filter ({{dt_undated_nodates}} undated results with no dates,
  {{dt_undated_filter}} with the filter).
- The Research endpoint has no date window (checked in the API reference on {{research_checked}}; not measured).
- Map returned nothing, silently, on {{map_official_empty}} of {{map_official}} official crawl-list sites (regulators, IOCL, Amul) and
  {{map_dairy_empty}} of {{map_dairy}} dairy sites.
- Scanned PDFs extract only the letterhead.

## Honest limits
{{cov_low}}–{{cov_high}} of the basket measured each month; recall {{arm_a_recall}} of {{known_changes}}; small
samples with Wilson intervals; {{custody_both}} of {{custody_total}} custody entries have both a request_id and a
response hash (later arms only); direct non-Tavily sources (MoSPI API, Department of Consumer Affairs (DoCA) download,
Wayback lookups); quote check (AI-assisted audit; pages then opened in a browser) {{q_verbatim}} verbatim,
{{q_paywalled}} paywalled, {{q_not_checked}} not checked; web news quotes ran in full only for {{web_quotes_month}}; searches
start {{pre_days}} days before the month, and v1's replay ran to month-end while the live seal stops at the
{{cutoff_day}}; v1 used `start_date`/`end_date` plus our own page-date check, and `filter_by_published_date` came later
(date test, radar, `timelock/`); an Uttar Pradesh (UP) electricity surcharge that may have been put on hold is left in
the score; a value-of-information score was dropped rather than tuned.
A Hindi substring match ('rail' inside 'domestic') turned a Jharkhand power tariff into a 'Bihar rail' event. Our
manual check caught it; the fix (whole-word matching, state from the page) removed the event, so the October radar
has {{radar_events_phrase}}. Logged as rule changes `R2`–`R3`, with before and after.

## Built with
Python, Streamlit, Tavily (Search, Extract; Map and Crawl trialled), NVIDIA Nemotron on Nebius Token Factory. Tavily
usage as of {{as_of}}: {{run_calls}} calls, {{run_credits}} credits, {{run_inside_pct}} of dated results inside the
requested window ({{run_inside}} of {{run_total}}), median latency {{run_latency}}.

## Try it
- App: https://shadow-cpi.streamlit.app
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
- Team: [TBD]
- Newly created during the submission period (opened {{submission_opened}}); first commit {{earliest_commit}}.
