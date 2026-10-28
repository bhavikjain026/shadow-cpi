# Shadow CPI: Devpost write-up

> Track: **Best Apps and Agents**. Bonus: Best Use of Tavily. Every number below is filled from the results files by
> `python tools/sync_doc_numbers.py`; edit `docs/templates/devpost.md`, not this file.

## Headline
<!-- headline:start -->
{{pool_dated}} of {{pool_cases}} cases detected leaking with Tavily's dates + filter, across a pilot and a pre-registered replication (Wilson {{pool_dated_w}}); with no dates, {{dt_nodates}} of {{dt_cases}} and {{rep_nodates}} of {{rep_cases}} leaked.
Reuse: `timelocked_search`, `extract_as_of`, Colab leak check.
<!-- headline:end -->

## Tagline
An AI agent that searches the past without cheating: it uses Tavily inside a time lock it cannot move, checks every
quote on its source page, and seals India's inflation forecast before the government publishes it.

In the forecast pipeline, NVIDIA Nemotron on Nebius Token Factory screens pages and cites quotes; code checks each cited number on the page.

## Short description
<!-- short:start -->
Can a search engine keep the past in the past? We measured Tavily's date controls on {{dt_cases}} replay cases
(pilot, pre-registered). With no dates, {{dt_nodates}} of {{dt_cases}} cases kept a confirmed leak, a page dated after
the cutoff with no archive copy before it (Wilson {{wilson}} {{dt_nodates_w}}; {{dt_nodates_retry}} of {{dt_cases}}
after retrying {{rr_dt_failed}} failed archive lookups); with `start_date`/`end_date` and
`filter_by_published_date`, {{dt_dated}} of {{dt_cases}} detected ({{dt_dated_w}}). The cost: the filter dropped
{{dt_lost_filter}} of {{dt_valid_total}} pieces of valid evidence (initial pass). Dates select pages, not versions. Shadow CPI puts this to work: an AI agent searches with Tavily
inside a time lock, checks each quote against the extracted page with NVIDIA Nemotron on Nebius Token Factory, lets
code compute India's {{live_month}} inflation nowcast, and seals it before the Ministry of Statistics publishes on
{{release_day}}.
<!-- short:end -->

## The leak, measured
- **Main result (date test, a pilot; the pre-registered initial pass):** no dates, {{dt_nodates}} of {{dt_cases}}
  cases leaked (Wilson {{wilson}} {{dt_nodates_w}}); `start_date`/`end_date` + `filter_by_published_date`,
  {{dt_dated}} of {{dt_cases}} detected ({{dt_dated_w}}). Update: {{dt_nodates_retry}} of {{dt_cases}}
  ({{dt_nodates_retry_w}}) and {{dt_dated_retry}} of {{dt_cases}} detected ({{dt_dated_retry_w}}) after retrying the
  {{rr_dt_failed}} archive lookups that had failed; the retry only re-ran those lookups, with the same labelling rules.
- **Dates or filter?** Explicit date windows already gave {{dt_datesonly}} of {{dt_cases}} detected (`start_date`/`end_date` only,
  Wilson {{dt_datesonly_w}}); the filter additionally drops undated pages (the dates-only search returned
  {{dt_undated_datesonly}} undated of {{dt_results_datesonly}} results here).
- **What a leak is.** A case leaks when at least one result the search kept is a confirmed leak, which
  `v2/DATE_TEST_PREREG.md` defines as: "{{dt_leak_rule}}" The finance check's rule differs
  (`v2/FINANCE_PREREG.md`, as amended): "{{fin_leak_rule}}" Its counts are reported apart and never added to the
  date test's. No-dates counts are lower bounds: a page the Wayback Machine never captured cannot be confirmed
  (absence from Wayback is not proof the page did not exist).
- **Replication and statistics:** {{rep_nodates}} of {{rep_cases}} with no dates, {{rep_dated}} of {{rep_cases}}
  detected with dates + filter (pre-registered); pooled {{pool_dated}} of {{pool_cases}} detected, rule of three below
  {{pool_r3}}; exact McNemar p = {{mcn_dt_p}} (date test), {{mcn_rep_p}} (replication), {{mcn_pool_p}} (pooled)
  ({{posthoc_label}}, `results/posthoc_stats.md`). Without the cache-served replication responses: {{rep_desc_nodates}}
  of {{rep_desc_cases}} and {{rep_desc_dated}} of {{rep_desc_cases}} detected (the logged addendum).
- **The cost (the measured cost of the strict setting):** the filter dropped {{dt_lost_filter}} of the date test's {{dt_valid_total}} pieces of valid evidence
  (initial pass; {{dt_lost_filter_retry}} of {{dt_valid_total_retry}} after the retry).
- **Date filters select which pages, not which version.** Tavily dated `{{ex_row}}`, a {{ex_company}} results
  preview, {{ex_published}}, before its {{ex_cutoff}} cutoff; the page was updated on {{ex_updated}} with a link to the
  actual result, and Extract returns the updated page. `max_age_hours` controls freshness, not as-of;
  `extract_as_of` fills that gap (demo, n={{asof_n}}).
- **Reuse:** `timelock/`, `mcp/`, `benchmarks/timelock34/`.

## Time-locked search leakage
- **Finance check** (exploratory; Reserve Bank of India (RBI) decisions and company results, its own rule above):
  no dates, {{fin_nodates}} of {{fin_events}} events on the pre-registered initial pass (Wilson {{wilson}}
  {{fin_nodates_w}}); with dates and the filter, {{fin_dated}} of {{fin_events}} detected ({{fin_dated_w}}). Update:
  {{fin_nodates_retry}} of {{fin_events}} ({{fin_nodates_retry_w}}) and {{fin_dated_retry}} of {{fin_events}} detected
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

## What Tavily's docs say vs what we measured
Tavily's API reference, quoted and linked, next to our measurement. Most of what we found is documented behaviour.

{{tavily_docs_table}}

## Search dates do not freeze page content
Date filters select which pages, not which version: a page dated before the cutoff can be updated after it, and
Extract returns the updated page. `max_age_hours` controls freshness, not as-of; `extract_as_of` fills that gap
(demo, n={{asof_n}}). Example (a separate,
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
templates found more. That is a result about query planning (what Nemotron chose to search for), not about
Tavily, which answered every arm; the likely cause is source choice (arm H differed from A only in domains and
language). An observation: `auto_parameters` with no dates reached for the present, {{auto_oct}} of {{auto_results}}
results from {{live_month}} ({{auto_note}}); Tavily documents `time_range` as counting back from the current date.
So the model chooses the query, topic, domains and language; code owns the dates.

## Tavily field notes / repro kit: feedback for the Most Valuable Feedback prize
Publishing these measurements was approved by <who, role> on <date> (<link>). Screenshot:
`docs/permission_2026-10-27.png`.

Full notes with request IDs and a one-request repro script each: `docs/tavily_bug_reports.md`. Each is tagged against
Tavily's docs: documented behaviour, doc gap or unexplained.

**Feature requests ({{feature_n}})**
1. **An as-of / crawl-timestamp field** (documented behaviour). Date filters select which pages, not which version:
   `{{ex_row}}` (above) was dated before the cutoff and updated after it, and Extract returns today's copy;
   `max_age_hours` controls freshness, not as-of. `extract_as_of` fills that gap (demo, n={{asof_n}}). *Evidence:*
   `results/timelock34_second_review.json`; the search's request ID is in the notes.
2. **Separate original-publication and last-modified dates** (documented behaviour): `published_date` was later
   than the page's own date on {{pd_later}} of {{pd_pages}} distinct date-test pages, as the documented definition
   (published or last updated, beta) allows.

**Observations**
- **`auto_parameters` picked a recent `time_range` for queries about a past month** (unexplained; {{auto_note}}):
  with no dates, on {{auto_searches}} searches naming a month in {{replay_span}}, {{auto_oct}} of {{auto_results}}
  results came from {{live_month}}. *Evidence:* `v2/ablation/arm_T_*.json`; request IDs in the notes.
- **With explicit dates, the `auto_parameters` echo still reports a `time_range`** (doc gap): on {{autod_searches}}
  searches with our `start_date`/`end_date`, the echo said `time_range` {{autod_ranges}} and held a start or end date
  in {{autod_echo_dates}} of them, while {{autod_inside}} of {{autod_dated}} dated results fell inside our window.
  *Suggested change:* echo `start_date`/`end_date` when dates are sent. *Evidence:* `v2/ablation/arm_Td_*.json`.
- Map's silent empty answer (unexplained) on {{map_official_empty}} of {{map_official}} official crawl-list sites and
  {{map_dairy_empty}} of {{map_dairy}} dairy sites (no error, no `failed_results`).
- On one scanned dairy rate-list PDF, Extract returned the letterhead but not the image-only rates (doc gap).
- `/usage` lag (doc gap): {{usage_endpoint}} credits on `/usage` against {{usage_per_call}} from per-call
  `include_usage`, the same day.

## Feedback by product: Nebius Token Factory, Nemotron Nano, Nemotron Super (and Tavily, separately)
{{feedback_five}}

## Inspiration
India's CPI arrives about {{release_lag}} days after the month ends. Forecasting it from the web means replaying past
months, and a replay that reads a page published after its cutoff looks better than it could ever be live. El Lahib et
al. ({{lahib_year}}, arXiv {{lahib_arxiv}}) found at least one retrieved page containing major post-cutoff leakage for
{{lahib_pct}} of Google-audited questions, after {{lahib_queries}} queries and about {{lahib_urls}} URLs each; our {{dt_nodates}}/{{dt_cases}}
on the pre-registered initial pass ({{dt_nodates_retry}}/{{dt_cases}} after the logged archive retry) is per search task, so the rates are not directly comparable. So we built a nowcast that tests, rather than assumes,
Tavily's date controls and measures what they cost.

## Related work
{{related_position}} Related studies, each checked on its arXiv page:

{{related_work}}

## How it works
1. **Tavily Search proposes** pages, every call with `start_date`/`end_date` (the later time-locked searches also send
   `filter_by_published_date`; v1's frozen search used the dates plus our page-date check); code re-checks each date.
2. **Tavily Extract reads the page:** the model returns a line number; code copies that line from the Extract output
   and checks the number is in it. A model never writes a quote.
3. **Plain code computes:** index levels combined with MoSPI's official weights; year-on-year last.
4. **The seal:** canonical JSON + `SHA-256` + a git tag. We publish the prediction's SHA-256 and a Git tag before
   release, so anyone can verify the file they have. The seal proves when the forecast was
   committed, not what was read before it; the time lock and `extract_as_of` address the evidence.

**How we use NVIDIA Nemotron on Nebius Token Factory:** Nano screens pages, Super cites the exact line, code checks
the number. Nemotron Nano (`{{nano_id}}`; from {{switch_day}} `{{nano_new}}`) is the yes/no
gatekeeper and writes display-only English glosses ({{nano_sent}} calls sent; {{nano_total}} including cache hits).
Nemotron Super (`{{super_id}}`; from {{switch_day}} `{{super_new}}`) reads pages, cites lines, and writes the search fields in arms B,
C and H ({{super_sent}} calls sent; {{super_total}} including cache hits). Nebius retires the original IDs on {{switch_day}}; from then, calls use Nebius's recommended replacements (pre-registered on {{migration_registered}}).
Where Token Factory helped (dated entries in `FEEDBACK_NOTES.md`): JSON-schema output worked on the opening call;
the `/models` list served both sizes behind one OpenAI-compatible endpoint, so roles are picked by name in config; and
having Super cite line numbers instead of copying text made Hindi pages work.

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
**Model memory:** the time lock controls what search returns, not what the models know. NVIDIA's model cards
(checked {{cutoffs_checked}}): Nemotron Nano pre-training {{nano_pre}}, post-training {{nano_post}}; Nemotron Super
pre-training {{super_pre}}, post-training {{super_post}}, inside the {{replay_span}} replay; replacement models:
{{new_models_cutoff}}. So the replay is not leakage-free against model memory; the sealed forward forecasts are the
clean evidence. Every zero is reported as zero detected, with its Wilson interval, and no-dates counts are lower bounds (absence
from Wayback is not proof a page did not exist).

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

## Testing instructions
1. **One minute, no key:** open the app's Leak demo (the opening screen: saved results, no API call), then the Field
   Report page for the full tables. Nothing is spent.
2. **Try it page, live on our credits:** ask a question with a cutoff; each run is two basic Tavily searches
   ({{tryit_run}} credits), at most {{tryit_session}} runs per visit and {{tryit_day}} credits a day for the page. A
   repeat of the same question and cutoff within {{tryit_cache}} hours is answered from that cached run for free. With
   no key the page shows a saved example; at the cap it says so and points to the Colab notebook.
3. **With your own Tavily key:** the Colab notebook (`notebooks/reproduce_leak.ipynb`, badge in the README) re-runs
   the leak check, and `repro/` holds one-request scripts for each field note. **Locally:** `pip install -r
   requirements-app.txt`, `streamlit run app.py` (no keys needed), `python -m pytest -q` (no keys, no credits).

## After the deadline
- **{{release_day}}, {{release_hour}} IST:** MoSPI publishes {{live_month}} CPI; we score the sealed nowcast against
  it with `score.py`, and the Archive page shows the miss and whether the figure was inside the range.
- **{{switch_day}}:** the dated model switch; calls from that day use Nebius's replacement models, logged per call.
- **About {{nov_seal}}:** the November seal, made with the replacement models and saying so.
- The judged version is the git tag `{{judged_tag}}`; anything committed later is labelled with its date.

## Try it
- App: https://shadow-cpi.streamlit.app
- Code: https://github.com/bhavikjain026/shadow-cpi (MIT licence)
- Verify a seal: `verify.md`
- Team: [TBD]
- Newly created during the submission period (opened {{submission_opened}}); first commit {{earliest_commit}}.
