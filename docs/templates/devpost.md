# Shadow CPI: Devpost write-up

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily. Every number below is filled from the results files by
> `python tools/sync_doc_numbers.py`; edit `docs/templates/devpost.md`, not this file.

## Headline
<!-- headline:start -->
{{pool_dated}} of {{pool_cases}} cases with Tavily's dates + filter, across a pilot and a pre-registered replication (Wilson {{pool_dated_w}}); with no dates, {{dt_nodates}} of {{dt_cases}} and {{rep_nodates}} of {{rep_cases}} leaked.
Reuse: `timelocked_search`, `extract_as_of`, Colab leak check.
<!-- headline:end -->

## Tagline
An AI agent that searches the past without cheating: it uses Tavily inside a time lock it cannot move, checks every
quote on its source page, and seals India's inflation forecast before the government publishes it.

Pages are screened and quotes cited by NVIDIA Nemotron (Nano and Super) on Nebius Token Factory; code checks every number.

## Short description
<!-- short:start -->
Can a search engine keep the past in the past? We measured Tavily's date controls on {{dt_cases}} replay cases
(pilot, pre-registered). With no dates, {{dt_nodates}} of {{dt_cases}} cases kept a confirmed leak, a page dated after
the cutoff with no archive copy before it (Wilson {{wilson}} {{dt_nodates_w}}; {{dt_nodates_retry}} of {{dt_cases}}
after retrying {{rr_dt_failed}} failed archive lookups); with `start_date`/`end_date` and
`filter_by_published_date`, {{dt_dated}} of {{dt_cases}} ({{dt_dated_w}}). The cost: the filter dropped
{{dt_lost_filter}} of {{dt_valid_total}} pieces of valid evidence (initial pass). Search dates do not freeze page content:
pages change after the cutoff. Shadow CPI puts this to work: an AI agent searches with Tavily
inside a time lock, checks each quote against the extracted page with NVIDIA Nemotron on Nebius Token Factory, lets
code compute India's {{live_month}} inflation nowcast, and seals it before the Ministry of Statistics publishes on
{{release_day}}.
<!-- short:end -->

## The leak, measured
- **Main result (date test, a pilot; the pre-registered initial pass):** no dates, {{dt_nodates}} of {{dt_cases}}
  cases leaked (Wilson {{wilson}} {{dt_nodates_w}}); `start_date`/`end_date` + `filter_by_published_date`,
  {{dt_dated}} of {{dt_cases}} ({{dt_dated_w}}). Update: {{dt_nodates_retry}} of {{dt_cases}}
  ({{dt_nodates_retry_w}}) and {{dt_dated_retry}} of {{dt_cases}} ({{dt_dated_retry_w}}) after retrying the
  {{rr_dt_failed}} archive lookups that had failed; the retry only re-ran those lookups, with the same labelling rules.
- **What a leak is.** A case leaks when at least one result the search kept is a confirmed leak, which
  `v2/DATE_TEST_PREREG.md` defines as: "{{dt_leak_rule}}" The finance check's rule differs
  (`v2/FINANCE_PREREG.md`, as amended): "{{fin_leak_rule}}" Its counts are reported apart and never added to the
  date test's.
- **The cost:** the filter dropped {{dt_lost_filter}} of the date test's {{dt_valid_total}} pieces of valid evidence
  (initial pass; {{dt_lost_filter_retry}} of {{dt_valid_total_retry}} after the retry).
- **Search dates do not freeze page content.** Tavily dated `{{ex_row}}`, a {{ex_company}} results preview,
  {{ex_published}}, before its {{ex_cutoff}} cutoff; the page was updated on {{ex_updated}} with a link to the actual
  result, and Extract returns the updated page.
- **Reuse:** `timelock/`, `mcp/`, `benchmarks/timelock34/`.

## Time-locked search leakage
- **Finance check** (exploratory; Reserve Bank of India (RBI) decisions and company results, its own rule above):
  no dates, {{fin_nodates}} of {{fin_events}} events on the pre-registered initial pass (Wilson {{wilson}}
  {{fin_nodates_w}}); with dates and the filter, {{fin_dated}} of {{fin_events}} ({{fin_dated_w}}). Update:
  {{fin_nodates_retry}} of {{fin_events}} ({{fin_nodates_retry_w}}) and {{fin_dated_retry}} of {{fin_events}}
  ({{fin_dated_retry_w}}) after the retry ({{rr_fin_failed}} lookups had failed).
- **Check P, full page** (exploratory): of {{p_pages}} pages that passed the date lock, {{p_later}} described a later
  event; most later dates were page furniture ({{p_furniture}} of {{p_flagged}} flagged pages: date bars, sidebars,
  related links).
- **Check E** (exploratory, `exact_match`): its misses are filter misses, not back-dating ({{e_missed_later}} of
  {{e_missed}} have a later `published_date`).

**Leak counts** (case level; the pre-registered initial pass is the primary count, after the logged archive retry is
the update):

{{leak_count_table}}

**Valid evidence kept** (initial pass; each check has its own denominator):

{{evidence_kept_table}}

## Search dates do not freeze page content
A page dated before the cutoff can be updated after it, and Extract returns the updated page. Example (a separate,
post-hoc AI-assisted review (ChatGPT agent); {{sr_unclear}} of {{sr_rows}} rows stayed unclear): `{{ex_row}}`, a
{{ex_company}} results preview, cutoff {{ex_cutoff}}; Tavily dated it {{ex_published}}, and the page was updated on
{{ex_updated}} with a link to the actual result. {{sr_fin_dated_after}} of {{sr_fin_searches}} filtered searches in
the finance check returned a result dated after the cutoff; that review found {{sr_fin_reviewer_leaks}} page whose current
version leaks the outcome. What covers the gap, partly: our page-date check (kept {{dt_results_pagecheck}} of
{{dt_results_filter}} filtered results in the date test; date-test valid evidence lost: {{dt_lost_pagecheck}} of
{{dt_valid_total}} with it (initial pass), {{dt_lost_filter}} with the filter alone; after the retry
{{dt_lost_pagecheck_retry}} and {{dt_lost_filter_retry}} of {{dt_valid_total_retry}}); the drift monitor, which re-reads October radar
pages daily ({{drift_phrase}}); and Wayback Machine checks, with failed lookups retried and logged
({{dt_retry_urls}} in the date test, {{fin_retry_urls}} in the finance check).

## Who writes the search: model-written fields vs fixed templates, inside a time lock it cannot move
Building on Tavily's dynamic-filtering idea, we let Nemotron write the search fields and tested it on
{{known_changes}} known price changes: code templates (arm A) found {{arm_a_recall}}, Nemotron-written fields (arms B
and C) {{arm_b_recall}} and {{arm_c_recall}}, `auto_parameters` (arm T) {{arm_t_recall}}; exploratory arm H
(templates + model-chosen fields) {{arm_h_recall}}, and T+dates {{arm_td_recall}}. The model's fields were always
valid ({{bc_fields_valid}} of {{bc_fields}}; {{arm_h_fields_valid}} of {{arm_h_fields}} in arm H), but fixed
templates found more; the likely cause is source choice (arm H differed from A only in domains and language).
Observed in our test, `auto_parameters` with no dates assumed "now": {{auto_oct}} of {{auto_results}} results came from {{live_month}} ({{auto_note}}).
So the model chooses the query, topic, domains and language; code owns the dates.

## What we found about Tavily: feedback for the Most Valuable Feedback prize
Publishing these measurements was approved by <who, role> on <date> (<link>). Screenshot:
`docs/permission_2026-10-27.png`.

Full reports with request IDs: `docs/tavily_bug_reports.md`.

**Top {{top_n}}**
1. **`auto_parameters` picks a recent `time_range` for queries about a past month.**
   *Observed:* with no dates, on {{auto_searches}} searches naming a month in {{replay_span}}, it chose recent time
   ranges; {{auto_oct}} of {{auto_results}} results came from {{live_month}} ({{auto_note}}). *Expected:* a window covering the month
   the query names, or none. *Suggested fix:* return no `time_range` (or that month's window) when the query names a
   past month; document the default. *Evidence:* `v2/ablation/arm_T_*.json`; request IDs in the report.
2. **With explicit dates, `auto_parameters` still reports a `time_range`.**
   *Observed:* on {{autod_searches}} searches with our `start_date`/`end_date`, the echo said `time_range`
   {{autod_ranges}} and held a start or end date in {{autod_echo_dates}} of them, while {{autod_inside}} of
   {{autod_dated}} dated results fell inside our window. *Expected:* the echo shows the window applied. *Suggested
   fix:* echo `start_date`/`end_date`, or drop `time_range`, when dates are sent. *Evidence:*
   `v2/ablation/arm_Td_*.json`; request IDs in the report.
3. **Extract has no as-of view, so Search dates do not freeze page content.**
   *Observed:* `{{ex_row}}` (above). *Expected:* a way to read, or at least detect, the page as it was on the cutoff.
   *Suggested fix:* an as-of / crawl-date field on Extract. *Evidence:* `results/timelock34_second_review.json`; the
   search's request ID is in the report.

**Feature requests**
- Separate original-publication and last-modified dates: `published_date` was later than the page's own date on
  {{pd_later}} of {{pd_pages}} distinct date-test pages, consistent with Tavily's documented definition (published or
  last updated, beta).

**Smaller observations**
- Map's silent empty answer on {{map_official_empty}} of {{map_official}} official crawl-list sites and
  {{map_dairy_empty}} of {{map_dairy}} dairy sites (no error, no `failed_results`).
- On one scanned dairy rate-list PDF, Extract returned the letterhead but not the image-only rates.
- `/usage` lag: {{usage_endpoint}} credits on `/usage` against {{usage_per_call}} from per-call `include_usage`, the
  same day.

## Feedback for Nebius and NVIDIA (Token Factory, Nemotron Nano, Nemotron Super)
**What each was used for.** *Nebius Token Factory* (`{{nebius_host}}`): the one OpenAI-compatible endpoint for every
model call, through `shadow_cpi/nemotron.py`. *Nemotron Nano* (`{{nano_id}}`): the yes/no gatekeeper ("does this page
state an Indian price or price change?") and display-only English glosses ({{nano_sent}} calls sent). *Nemotron
Super* (`{{super_id}}`): reads each page as numbered lines and cites the line for every price and price change;
writes the search fields in arms B, C and H ({{super_sent}} calls sent).

**What worked well.**
- JSON-schema output worked on the opening call (`checks.py`, "[PASS] Nemotron JSON output"), so every answer is
  parsed, not guessed. Every call sends `response_format` with a strict schema; a refusal falls back to JSON mode
  with the schema in the prompt (logged from {{migration_registered}}). Both of Nebius's replacement models accepted the
  same schema request in a smoke test on {{migration_registered}} (`results/model_migration_smoke.json`).
- One endpoint for both sizes: the cheap gatekeeper and the careful reader are a config change apart
  (`config/models.json`).
- Citing line numbers instead of copying text made Hindi pages work: the model returns a line number, code copies
  that line from the Extract output and checks the number is in it.

**What needs work.**
- Nano returned no number on pages where Super, re-reading the same page, found one: Super re-read
  {{nano_null_rereads}} pages and found a verified number on {{nano_null_found}}. A schema hint ("a number is required
  when the line has a currency or %"), or a confidence field, would help.
- Nano, as gatekeeper, said "no" to a page that plainly listed rupee prices (a Delhi vegetable-price page); we added
  a code backstop so a page with a visible rupee price is never skipped.
- Super sometimes labelled the item from the page's context rather than the cited line, and took the low end of a
  price range; code now requires the item name in the cited line.
- Reliability: one read timeout and one connection reset each stopped a long run; our client now retries timeouts.
  The `/models` list mixes naming styles (case, `3.5` vs `3_5`), and a vision model sits next to the text models, so
  picking by name needs care.
- Billing onboarding was confusing: the free trial, a separate promo balance and the 'paid usage after trial' switch
  were hard to tell apart, and with a card saved we couldn't be sure the card wouldn't be charged, so we kept paid
  usage off.

**Onboarding, from zero to hello world.** Put the key in `.env`, point any OpenAI-compatible client at the endpoint,
call `/models`, then one chat completion with a JSON schema: that is `checks.py`, and it passed on the opening call.
The step that took care was choosing model IDs from the `/models` list.

**Would we build with them again?** Yes: one endpoint with a small and a large model, strict JSON-schema output, and
line-number citing let code, not the model, decide every number. We would ask for the fixes above.

## Inspiration
India's CPI arrives about {{release_lag}} days after the month ends. Forecasting it from the web means replaying past
months, and a replay that reads a page published after its cutoff looks better than it could ever be live. El Lahib et
al. ({{lahib_year}}, arXiv {{lahib_arxiv}}) found at least one retrieved page containing major post-cutoff leakage for
{{lahib_pct}} of Google-audited questions, after {{lahib_queries}} queries and about {{lahib_urls}} URLs each; our {{dt_nodates}}/{{dt_cases}}
on the pre-registered initial pass ({{dt_nodates_retry}}/{{dt_cases}} after the logged archive retry) is per search task, so the rates are not directly comparable. So we built a nowcast that tests, rather than assumes,
Tavily's date controls and measures what they cost.

## Related work
{{related_work}}

## How it works
1. **Tavily Search proposes** pages, every call with `start_date`/`end_date` (the later time-locked searches also send
   `filter_by_published_date`; v1's frozen search used the dates plus our page-date check); code re-checks each date.
2. **Tavily Extract reads the page:** the model returns a line number; code copies that line from the Extract output
   and checks the number is in it. A model never writes a quote.
3. **Plain code computes:** index levels combined with MoSPI's official weights; year-on-year last.
4. **The seal:** canonical JSON + `SHA-256` + a git tag. We publish the prediction's SHA-256 and a Git tag before
   release, so anyone can verify the file they have.

**NVIDIA Nemotron on Nebius Token Factory:** Nemotron Nano (`{{nano_id}}`; from {{switch_day}} `{{nano_new}}`) is the yes/no
gatekeeper and writes display-only English glosses ({{nano_sent}} calls sent; {{nano_total}} including cache hits).
Nemotron Super (`{{super_id}}`; from {{switch_day}} `{{super_new}}`) reads pages, cites lines, and writes the search fields in arms B,
C and H ({{super_sent}} calls sent; {{super_total}} including cache hits). Nebius retires the original IDs on {{switch_day}}; from then, calls use Nebius's recommended replacements (pre-registered on {{migration_registered}}).
Token Factory helped: every call asks for JSON-schema output (with a logged JSON-mode fallback); schema output
worked on the opening call, and both sizes sit behind one OpenAI-compatible endpoint, so roles are a config change.

## What it does
- **The {{live_month}} nowcast.** {{seal_status}}. {{live_month}} CPI is scheduled for {{release_day}} at {{release_hour}} IST (MoSPI's
  next-working-day rule applies).
  Anyone can recompute the seal's `SHA-256` from the file at tag `seal-2026-10` (`verify.md`).
- **Price Shock Radar** (exploratory, report only): announced price changes taking effect this month;
  {{radar_events}} verified so far, {{radar_corroborated}} corroborated.
- **Live build** with **Replay a saved run** (no API call, no credits).
- **Chain of custody** from any number to its quote, page, Tavily request ID, response hash and seal; **`as_of()`**
  shows what was known on a past day.

## Reuse
`timelock/` (time-locked search, standard library only), `mcp/` (the same as an MCP tool), the benchmark
`benchmarks/timelock34/` ({{tl_cases}} cases, {{tl_questions}} distinct questions (two pairs share a question and its
searches); new URLs a search returns are unlabelled until reviewed and are never counted as safe), `shadow_cpi/pit` (`pit_search(query, cutoff)`) and the agent skill `skills/time-locked-search/SKILL.md`. **For
research teams:** designed for event studies and backtests that must not see the outcome early; research tool, not
investment advice.

## Scoreboard
{{replay_span}} replay, pre-registered, with one disclosed post-scoring correction ({{mae_c_before}} → {{mae_c}};
`results/score_lock.json`): Shadow CPI v1 {{mae_c}} pp mean miss,
trend only {{mae_trend}}, repeat-last-month {{mae_b1}}. On the {{poll_months}} poll months: {{mae_poll_c}} vs the
poll's {{mae_poll}}, about a tie. The {{range_level}} range held in {{inside}} of {{months}} months. v2 was not
better ({{mae_v2}}).

## Honest limits
{{cov_low}}–{{cov_high}} of the basket measured each month; recall {{arm_a_recall}} of {{known_changes}}; small,
India-focused samples with Wilson intervals ({{dt_cases}} date-test cases and {{fin_events}} finance events show the effect
exists and its size here, not Tavily's behaviour in general); data vintage: MoSPI began publishing the {{base_year}}-base
series (with its {{base_history_year}} history) on {{base_published}}, so a real {{base_first_month}} nowcast could not
have used that history, while our {{base_first_month_short}} replay did (from {{base_public_from}} on it was public before
each nowcast); every case whose label changed after the archive retry ({{retry_changed}} of {{retry_cases}}) is listed
in `docs/retry_reconciliation.md`; {{custody_both}} of {{custody_total}} custody entries have both a request_id and a
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
Exploratory and post-hoc results are labelled where they appear and changed no scored verdict.

## Built with
- Nebius Token Factory
- `{{nano_id}}` (until {{switch_last_day}}), then `{{nano_new}}`
- `{{super_id}}` (until {{switch_last_day}}), then `{{super_new}}`

Nebius retires the original IDs on {{switch_day}}; from then, calls use Nebius's recommended replacements (pre-registered on {{migration_registered}}).

- Tavily API
- Python
- Streamlit

Tavily usage as of {{as_of}}: {{run_calls}} calls, {{run_credits}} credits, {{run_inside_pct}} of dated results
inside the requested window ({{run_inside}} of {{run_total}}), median latency {{run_latency}}. Third-party notices:
`THIRD_PARTY_NOTICES.md`.

## Try it
- App: https://shadow-cpi.streamlit.app
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
- Team: [TBD]
- Newly created during the submission period (opened {{submission_opened}}); first commit {{earliest_commit}}.
