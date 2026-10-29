# Shadow CPI

[![tests](https://github.com/bhavikjain026/shadow-cpi/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/bhavikjain026/shadow-cpi/actions/workflows/tests.yml)

## Can a search engine keep the past in the past? We measured Tavily's date controls.

**Time-locked web evidence for AI on Tavily: date-bounded search, as-of reading from archives (or a refusal), and code-checked citations, used to seal India's monthly inflation estimate.**

In the forecast pipeline, NVIDIA Nemotron on Nebius Token Factory screens pages and cites quotes; code checks each cited number on the page.

| Leaks, measured (pre-registered initial pass) | No dates | Dates + filter |
|---|---|---|
| Date test ({{dt_cases}} cases) | **{{dt_nodates}} of {{dt_cases}}** (Wilson {{dt_nodates_w}}) | **{{dt_dated}} of {{dt_cases}} detected** (Wilson {{dt_dated_w}}) |
| Replication ({{rep_cases}} new cases, pre-registered) | **{{rep_nodates}} of {{rep_cases}}** (Wilson {{rep_nodates_w}}) | **{{rep_dated}} of {{rep_cases}} detected** (Wilson {{rep_dated_w}}) |
| Finance check ({{fin_events}} cases, exploratory, different leak rule) | {{fin_nodates}} of {{fin_events}} ({{fin_nodates_w}}) | {{fin_dated}} of {{fin_events}} detected ({{fin_dated_w}}) |

Pilot + replication, date-test rule (pre-registered secondary): dates + filter {{pool_dated}} of {{pool_cases}} detected (Wilson {{pool_dated_w}};
post-hoc rule of three: below {{pool_r3}}). No-dates counts are lower bounds: a leak counts only when the Wayback
Machine confirms it, and a page the archive never captured is not counted (absence from Wayback is not proof the page
did not exist). Explicit date windows already gave {{dt_datesonly}} of {{dt_cases}} detected (`start_date`/`end_date` only,
Wilson {{dt_datesonly_w}}); the filter additionally drops undated pages (the dates-only search returned
{{dt_undated_datesonly}} undated of {{dt_results_datesonly}} results here).

Separate rules; never added together. **Update:** date test {{dt_nodates_retry}} of {{dt_cases}} with no dates (Wilson
{{dt_nodates_retry_w}}) after retrying the {{rr_dt_failed}} archive lookups that had failed, still {{dt_dated_retry}} of
{{dt_cases}} detected with dates + filter; finance check {{fin_nodates_retry}} of {{fin_events}} ({{fin_nodates_retry_w}}) after the
retry ({{rr_fin_failed}} lookups had failed), still {{fin_dated_retry}} of {{fin_events}} detected with dates + filter.

| | |
|---|---|
| [![{{alt_leak_demo}}](docs/gallery/1_leak_demo.png)](docs/gallery/README.md#the-opening-screen) | [![{{alt_four_arm}}](docs/gallery/2_four_arm_table.png)](docs/gallery/README.md) |
| [![{{alt_timeline}}](docs/gallery/3_r196_timeline.png)](docs/gallery/README.md) | [![{{alt_flow}}](docs/gallery/4_flow.png)](docs/gallery/README.md) |

<details>
<summary>Footnote: what counts as a leak, and the update after the archive retry</summary>

- **Dates + filter** means `start_date`/`end_date` plus `filter_by_published_date`; no dates means neither.
- **Date test** (pilot, replay cases; [`v2/DATE_TEST_PREREG.md`](v2/DATE_TEST_PREREG.md)). A case leaks when at least
  one result the search kept is a confirmed leak: "{{dt_leak_rule}}"
- **Replication** ({{rep_cases}} new cases, none from the pilot; [`v2/REPLICATION_PREREG.md`](v2/REPLICATION_PREREG.md)).
  The date test's leak rule and arms (no dates; dates + filter), cutoff the day before each price change, run once
  ([`results/replication.md`](results/replication.md)). The pooled line adds pilot and replication under the same rule,
  as pre-registered (secondary).
- **Cache note on the replication** (logged addendum in `results/replication.md`; descriptive, not pre-registered).
  Every call goes through our cache, and {{rep_cached}} no-dates answers were served from it, {{rep_cached_pilot}} of
  them the pilot's own response to the same query; the time-locked searches were all fresh. Without the
  {{rep_cached_pilot}} cases that reused the pilot's response: no dates {{rep_desc_nodates}} of {{rep_desc_cases}}
  (Wilson {{rep_desc_nodates_w}}), dates + filter {{rep_desc_dated}} of {{rep_desc_cases}} ({{rep_desc_dated_w}}). The
  pooled no-dates count ({{pool_nodates}} of {{pool_cases}}) includes that reused pilot response.
- **Finance check** (exploratory, Reserve Bank of India (RBI) decisions and company results;
  [`v2/FINANCE_PREREG.md`](v2/FINANCE_PREREG.md), as amended). A different rule, so its counts are reported apart:
  "{{fin_leak_rule}}"
- **Initial pass** (the table): the pre-registered result and the primary count.
- **The update, after the logged archive retry.** A logged retry re-ran only the archive lookups that had failed, with
  the same labelling rules. On the initial pass, {{rr_fin_failed}} finance-check archive lookups (and {{rr_dt_failed}} in the date test) failed
  for network reasons, so those pages could only be flagged, not confirmed; the retry recovered {{rr_recovered}},
  which is why the finance count rises from {{fin_nodates}} to {{fin_nodates_retry}} of {{fin_events}}. Wilson {{wilson}} intervals
  after the retry: date test no dates {{dt_nodates_retry_w}}, dates + filter {{dt_dated_retry_w}}; finance check no
  dates {{fin_nodates_retry_w}}, dates + filter {{fin_dated_retry_w}}.
- **Statistics ({{posthoc_label}}; [`results/posthoc_stats.md`](results/posthoc_stats.md)).** Exact McNemar, no
  dates vs dates + filter, paired by case on the initial pass: date test p = {{mcn_dt_p}}, replication p =
  {{mcn_rep_p}}, finance check p = {{mcn_fin_p}}, pooled p = {{mcn_pool_p}}. For the pooled {{pool_dated}} of
  {{pool_cases}} detected, the rule of three puts the leak rate below {{pool_r3}} with about {{wilson}} confidence (exact
  one-sided bound {{pool_exact1s}}). Without the cache-served replication responses: no dates {{rep_desc_nodates}} of
  {{rep_desc_cases}}, dates + filter {{rep_desc_dated}} of {{rep_desc_cases}} detected (the logged addendum, reused).

</details>

**The cost.** The measured cost of the strict setting: the filter dropped {{dt_lost_filter}} of the date test's
{{dt_valid_total}} pieces of valid evidence (initial pass; {{dt_lost_filter_retry}} of {{dt_valid_total_retry}} after
the retry).

**Date filters select which pages, not which version.** Tavily dated `{{ex_row}}`, a {{ex_company}} results preview,
{{ex_published}}, before its {{ex_cutoff}} cutoff; the page was updated on {{ex_updated}} with a link to the actual
result, and Extract returns the updated page. `max_age_hours` controls freshness, not as-of; `extract_as_of` fills that
gap (demo, n={{asof_n}}) ([details](#search-dates-do-not-freeze-page-content)). What Tavily's own docs say about each field,
next to what we measured: [below](#what-tavilys-docs-say-vs-what-we-measured).

**Reuse it:** [`timelock/`](timelock/) (time-locked search, standard library only,
[{{example_lines}}-line example](#use-it-in-{{example_lines}}-lines)) · [`mcp/`](mcp/README.md) (the same as an MCP
tool) · [`benchmarks/timelock34/`](benchmarks/timelock34/DATASHEET.md) (the labelled benchmark and scorer) · [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/bhavikjain026/shadow-cpi/blob/main/notebooks/reproduce_leak.ipynb) reproduce the leak with your own Tavily key ([`repro/`](repro/README.md) for the Tavily items).

**Live app:** https://shadow-cpi.streamlit.app · **Demo video:** [TBD] · **Devpost:** [TBD]

> **Required technologies**
>
> - **Nebius Token Factory**, endpoint host `{{nebius_host}}` (OpenAI-compatible; [`shadow_cpi/nemotron.py`](shadow_cpi/nemotron.py))
> - **NVIDIA Nemotron Nano**, `{{nano_id}}` (from {{switch_day}}: `{{nano_new}}`): yes/no gatekeeper ("does this page state an Indian price or price
>   change?") and display-only English glosses
> - **NVIDIA Nemotron Super**, `{{super_id}}` (from {{switch_day}}: `{{super_new}}`): reads the page and cites the line for each price and price change;
>   writes the search fields in arms B, C and H
> - Model roles: [`config/models.json`](config/models.json). Nebius retires the original IDs on {{switch_day}}; from then, calls use Nebius's recommended replacements (pre-registered on {{migration_registered}}).
> - **Tavily API** endpoints used: {{tavily_endpoints}} (and `/usage` for the balance)

## Time-locked search leakage

The Tavily field report (app page "Tavily field report", built by `tools/build_field_report.py` into
[`results/field_report.json`](results/field_report.json)), summarised. Each check has its own pre-registered leak
rule and its own count; date-test and finance counts are never added together.

- **Date test (pilot, {{dt_cases}} replay cases, [`v2/DATE_TEST_PREREG.md`](v2/DATE_TEST_PREREG.md)).** Rule quoted
  above. Pre-registered initial pass: no dates {{dt_nodates}} of {{dt_cases}} ({{dt_nodates_w}}), dates + filter
  {{dt_dated}} of {{dt_cases}} detected ({{dt_dated_w}}). Update: {{dt_nodates_retry}} of {{dt_cases}} and {{dt_dated_retry}}
  of {{dt_cases}} after retrying the {{rr_dt_failed}} archive lookups that had failed. Every case whose label changed
  after the retry ({{retry_changed}} of {{retry_cases}}, both checks), with the reason:
  [`docs/retry_reconciliation.md`](docs/retry_reconciliation.md).
- **Finance check (exploratory, {{fin_events}} Reserve Bank of India (RBI) decisions and company results,
  [`v2/FINANCE_PREREG.md`](v2/FINANCE_PREREG.md)).** Rule quoted above (it also needs the title or snippet to state
  the outcome). The day-before search with no dates leaked the outcome for {{fin_nodates}} of {{fin_events}}
  events on the pre-registered initial pass (Wilson {{wilson}} {{fin_nodates_w}}); with dates and the filter,
  {{fin_dated}} of {{fin_events}} detected ({{fin_dated_w}}). Update: {{fin_nodates_retry}} of {{fin_events}}
  ({{fin_nodates_retry_w}}) and {{fin_dated_retry}} of {{fin_events}} ({{fin_dated_retry_w}}) after the retry
  ({{rr_fin_failed}} lookups had failed).
- **Tasks and calls.** Each task sent one search per setting, so call counts equal task counts
  ({{dt_leak_calls_nodates}} of {{dt_calls_nodates}} date-test calls and {{fin_leak_calls_nodates}} of
  {{fin_calls_nodates}} finance calls with no dates leaked on the initial pass;
  [`results/date_field_test.json`](results/date_field_test.json),
  [`results/finance_lookahead.json`](results/finance_lookahead.json)).
- **Check P, full page (exploratory, [`results/leakcheck_full_page.md`](results/leakcheck_full_page.md)).** Of
  {{p_pages}} pages that passed the date lock (Tavily's filter, or our own date check), {{p_later}} described an event
  after the cutoff. {{p_flagged}} pages held a later date somewhere in the text, mostly as page furniture; each has
  one outcome: {{p_later}} later content (the page just counted), {{p_furniture}} in date bars, sidebars and related
  links, {{p_benign}} benign, {{p_unclear}} unclear.
- **Receipt.** Credits and latency per setting are in the table; every call is in the flight recorder and the
  credit ledger.

**Leak counts** (case level; the pre-registered initial pass is the primary count, after the logged archive retry is
the update):

{{leak_count_table}}

**Valid evidence kept** (initial pass; each check has its own denominator):

{{evidence_kept_table}}

With our extra page-date check added to the filter, {{dt_lost_pagecheck}} of the date test's {{dt_valid_total}}
pieces of valid evidence were lost (initial pass; {{dt_lost_pagecheck_retry}} of {{dt_valid_total_retry}} after the
retry). Check E's misses are filter misses, not back-dating: {{e_missed_later}} of
{{e_missed}} have a Tavily `published_date` after the cutoff ({{e_missed_earlier}} on or before it,
{{e_missed_undated}} undated; [`results/leakcheck_exact_match.md`](results/leakcheck_exact_match.md)).

Small samples: every rate in the field report carries a Wilson interval ({{wilson}}).

## What Tavily's docs say vs what we measured

Each row quotes Tavily's API reference ([Search]({{tavily_search_url}}), [Extract]({{tavily_extract_url}})) and puts
our measurement next to it. Most of what we found is documented behaviour; the field notes below tag each item
"documented behaviour", "doc gap" or "unexplained".

{{tavily_docs_table}}

## Search dates do not freeze page content

Date filters select which pages, not which version: Tavily's date filter works on a page's publish or last-updated
date, and Extract returns the page as it is when we call it. A page dated before the cutoff can be updated after it,
and the filter cannot see that. `max_age_hours` bounds how fresh Tavily's cached copy is (freshness, not as-of), and
the Extract reference lists no date field. `extract_as_of` fills that gap (demo, n={{asof_n}}, below). Example (from a separate, post-hoc AI-assisted
review (ChatGPT agent); {{sr_unclear}} of {{sr_rows}} rows stayed unclear): `{{ex_row}}`, a {{ex_company}} results
preview in the finance check, cutoff {{ex_cutoff}}. Tavily dated it {{ex_published}}, before the cutoff; the page
was updated on {{ex_updated}} with a link to the actual result. In the finance check, {{sr_fin_dated_after}} of
{{sr_fin_searches}} filtered searches returned a result dated after the cutoff, and that review still found
{{sr_fin_reviewer_leaks}} page whose current version leaks the outcome. Three things cover the gap, none of them
completely:

- **Our page-date check** reads the date printed on the extracted page and drops anything after the cutoff. In the
  date test it kept {{dt_results_pagecheck}} of the {{dt_results_filter}} results the filter let through; with it,
  {{dt_lost_pagecheck}} of the date test's {{dt_valid_total}} pieces of valid evidence were lost ({{dt_lost_filter}} with the filter
  alone; initial pass). It reads a page's date, not its edit history.
- **The drift monitor** re-reads each October radar page with Extract once a day and compares it with the saved copy
  ([`v2/DRIFT_PREREG.md`](v2/DRIFT_PREREG.md)): {{drift_phrase}}.
- **The Wayback Machine** shows whether a page existed by the cutoff; a leak counts only when it confirms one. Failed
  lookups were retried and logged ({{dt_retry_urls}} in the date test, {{fin_retry_urls}} in the finance check). In
  the post-hoc review, {{sr_unclear}} of {{sr_rows}} rows stayed unclear, partly because archive lookups were
  rate-limited.

## Who writes the search: model-written fields vs fixed templates, inside a time lock it cannot move

Tavily's dynamic filtering lets a model choose its own search fields. We built on that idea and tested it on
{{known_changes}} known retail price changes in {{replay_span}} (pre-registered in
[`v2/PREREGISTRATION.md`](v2/PREREGISTRATION.md); [`results/v2_ablation.md`](results/v2_ablation.md)):

| Arm | Who writes the search | Known changes found |
|---|---|---|
| A | code, fixed templates | {{arm_a_recall}} of {{known_changes}} |
| B | Nemotron Super (English, Hindi) | {{arm_b_recall}} of {{known_changes}} |
| C | Nemotron Super ({{arm_c_langs}} languages: English, Hindi and regional) | {{arm_c_recall}} of {{known_changes}} |
| T | Tavily `auto_parameters`, no dates | {{arm_t_recall}} of {{known_changes}} |
| H (exploratory, added after scoring) | templates + model-chosen fields | {{arm_h_recall}} of {{known_changes}} ({{arm_h_l4l}} vs A's {{arm_h_l4l_a}} on the {{arm_h_l4l_months}} months H completed) |
| T+dates (exploratory, added after scoring) | `auto_parameters` + our dates | {{arm_td_recall}} of {{known_changes}} ({{arm_td_complete}} of {{arm_td_months}} months complete) |

- **The fields were always valid.** Every field the model wrote was a proper Tavily parameter, dates included:
  {{bc_fields_valid}} of {{bc_fields}} searches in arms B and C, {{arm_h_fields_valid}} of {{arm_h_fields}} in arm H.
- **Fixed templates still found more.** This is a result about query planning (what Nemotron chose to search for),
  not about Tavily: the same Tavily endpoint answered every arm. The likely cause is source choice: arm H differed
  from arm A only in `include_domains` ({{arm_h_diff_domains}} searches) and `language` ({{arm_h_diff_language}}).
- **`auto_parameters` with no dates reached for the present (an observation).** On {{auto_searches}} searches about
  past months it picked recent time ranges, and {{auto_oct}} of {{auto_results}} results were from {{live_month}}
  ({{auto_note}}); Tavily documents `time_range` as counting back from the current date. With our dates added,
  {{autod_inside}} of {{autod_dated}} dated results fell inside the window.

So the time lock lives in code: the model may choose the query, topic, domains and language; code owns the dates.

## Tavily field notes / repro kit

Publishing these measurements was approved by <who, role> on <date> (<link>).
Screenshot: [`docs/permission_2026-10-27.png`](docs/permission_2026-10-27.png).

Full notes with observed / expected / suggested change / evidence (counts and Tavily request IDs) and a one-request
repro script each: [`docs/tavily_bug_reports.md`](docs/tavily_bug_reports.md), built from
[`results/bug_reports.json`](results/bug_reports.json). Each is tagged against Tavily's docs: **documented behaviour**,
**doc gap** or **unexplained**.

**Feature requests ({{feature_n}})**

- **An as-of / crawl-timestamp field** (documented behaviour). Date filters select which pages, not which version:
  `{{ex_row}}` (above) was dated before the cutoff and updated after it, and Extract returns today's copy.
  `max_age_hours` controls freshness, not as-of. `extract_as_of` fills that gap (demo, n={{asof_n}}); a field saying when the
  returned copy was fetched would let any time-locked user check it.
- **Separate original-publication and last-modified dates** (documented behaviour). `published_date` was later than
  the page's own date on {{pd_later}} of {{pd_pages}} distinct date-test pages, as Tavily's documented definition
  (published or last updated, beta) allows.

**Observations**

- **`auto_parameters` picked a recent `time_range` for queries about a past month** (unexplained;
  {{auto_note}}). With no dates, on {{auto_searches}} searches naming a month in {{replay_span}}, {{auto_oct}} of
  {{auto_results}} results came from {{live_month}}.
- **With explicit dates, the `auto_parameters` echo still reports a `time_range`** (doc gap). On {{autod_searches}}
  searches with our `start_date`/`end_date`, the echo said `time_range` {{autod_ranges}} and held a start or end date
  in {{autod_echo_dates}} of them, while {{autod_inside}} of {{autod_dated}} dated results fell inside our window: the
  dates were applied, the echo does not say so.
- **Map's silent empty answer** (unexplained): {{map_official_empty}} of {{map_official}} official crawl-list sites
  (state electricity regulators, IOCL, Amul) and {{map_dairy_empty}} of {{map_dairy}} dairy sites, with no error or
  `failed_results`.
- **One scanned PDF** (doc gap): on one scanned dairy rate-list PDF, Extract returned the letterhead but not the
  image-only rates.
- **`/usage` lag** (doc gap): `/usage` reported {{usage_endpoint}} credits used while per-call `include_usage` added
  up to {{usage_per_call}} the same day.

Also measured: the filter drops undated pages ({{dt_undated_nodates}} of {{dt_results_nodates}} results undated with
no dates, {{dt_undated_filter}} with the filter), and the Research endpoint has no date window (checked in the API
reference on {{research_checked}}; not measured).

## Tavily integration map

Every Tavily endpoint and parameter we use or refuse, what we do with it and why; each row is checked against the code
in `tests/test_sync_doc_numbers.py`.

{{tavily_map_table}}

## Reuse it

### Use it in {{example_lines}} lines

Install the time-lock package alone (works once the `submission-v1.0` tag exists, from Friday; until then
install from a clone with `pip install .`):

```bash
pip install "git+https://github.com/bhavikjain026/shadow-cpi@submission-v1.0"
```

[`timelock/`](timelock/) needs no part of the CPI pipeline and no package outside the Python standard library.
`timelocked_search(client, query, cutoff, **tavily_kwargs)` sends `start_date`/`end_date` and
`filter_by_published_date=true`, refuses an `end_date` after the cutoff (or `time_range`, `days`,
`auto_parameters`, or the filter switched off) before any call, and returns Tavily's results, each with
`published_date`, `page_date` (when the page text was extracted), `status` (`safe` / `date_flag` / `leak`),
`request_id` and `response_sha256`. A result dated after the cutoff is a `leak` even if Tavily's filter let it through.
A cutoff date means the end of that day in UTC: results dated on or before it (in UTC) pass; for IST, a page published `00:00–05:30` IST on the next day still counts as the cutoff day, so pass the previous day if you need a strict IST cutoff.

The cutoff day is inside the window. `end_date` is sent as the cutoff itself, never the day after (Tavily's reference
says only "before the specified end date", so we do not rely on it keeping that day; at worst we lose cutoff-day pages),
and a `published_date` counts by its UTC calendar date against the cutoff date: a page stamped
`Tue, 06 Oct 2026 23:59:59 GMT` is safe at cutoff `2026-10-06`, `Wed, 07 Oct 2026 00:00:00 GMT` is a `leak`. Edge: a
page published after `18:30` UTC on the cutoff day is already the next day in IST but is labelled `safe`; pick the day
before as the cutoff if that matters.

```python
import sys
from pathlib import Path

from timelock import Replay, TavilyHTTP, timelocked_search

saved = Path(__file__).resolve().parent.parent / "tests/fixtures/timelock/rbi_2026-10-06_locked.json"
client = TavilyHTTP() if "--live" in sys.argv else Replay(saved)          # live costs 1 Tavily credit
results = timelocked_search(client, "RBI monetary policy repo rate decision October 2026", cutoff="2026-10-06",
                            topic="news", search_depth="basic", max_results=5, include_published_date=True)
for r in results:
    print(r["status"], r["published_date"], r["url"])
print(results.counts, results.request_id, results.response_sha256[:12])
```

```bash
python -m examples.timelock_rbi                              # offline: a saved Tavily response, 0 credits
TAVILY_API_KEY=... python -m examples.timelock_rbi --live    # live
```

Offline it replays a real saved response (`tests/fixtures/timelock/`, request ID and hash checked in
[`tests/test_timelock.py`](tests/test_timelock.py)); `Replay` refuses any other request. Any client with
`.search(query, **kwargs) -> dict` works, including tavily-python's `TavilyClient`.

- **LangChain:** `TimeLockedTavilySearch(cutoff=...)` in [`timelock/langchain.py`](timelock/langchain.py) is a drop-in search tool for an agent's tool list with a fixed cutoff, `time_range`/`days`/`auto_parameters` refused and only `safe` results returned (`pip install ".[langchain]"`; [short example](examples/langchain_timelock.py)).
- **MCP `check_leaks(results_json, cutoff)`:** audits results from any search tool with no API call: counts safe / undated / after-cutoff and lists the URLs to re-read with `extract_as_of` ([`mcp/`](mcp/README.md)).

### Report back to Tavily (optional, off by default)

Tavily's feedback endpoint (`POST https://api.tavily.com/feedback`) is in beta: its docs say the request shape may still change and that a failure should be treated as non-fatal. Submitting feedback is free and uses no API credits ([reference](https://docs.tavily.com/documentation/api-reference/endpoint/feedback)). This is off by default. `check_leaks(..., report_to_tavily=True)` on the MCP server reports only results our check labels `leak`, and only from our own date-filtered requests: the request must be one this server made (or one listed in the file named by `TIMELOCK_LEDGER`) and must have sent an `end_date`. Undated control searches are never reported, because a leak there is not a fault of Tavily's filter. It needs `TAVILY_API_KEY` and sends the leaking result's URL and the dates we saw, so leave it off unless you want that. In code, `timelock.send_feedback(...)` is a dry run unless you pass `dry_run=False`, and a failed send is returned, not raised.

### Read a page as it was on the cutoff

Search dates do not freeze page content: Extract returns a page as it is today, so a page dated before the cutoff
can carry a link to the result it previewed. `extract_as_of(client, url, cutoff)` extracts the live page and checks
its change evidence (Tavily's date, the page's own published/updated date, Wayback captures). If the page may have
changed after the cutoff it returns the latest Wayback capture on or before the cutoff instead, with provenance
`{source: "tavily_live" | "wayback_asof", capture_time, reason}` (plus `capture_timestamp` and `capture_digest` for a
Wayback copy; only captures with status `200` on or before the cutoff are used); if there is no such capture, it returns no text
and the reason `no as-of copy`, never the live page. When nothing suggests a change but the Wayback Machine holds no
capture on or before the cutoff, the live page comes back labelled `unverified: no archive copy before the cutoff`;
pass `strict=True` to refuse it instead. If Extract answers for a different address (compared ignoring the scheme and
a trailing slash), it returns no text and the reason `url mismatch`, never another page's text. Wayback is a direct
download outside Tavily.

Two demos (one page each, not a measurement): on {{asof_refused_row}} it refused, because the Wayback Machine holds
no copy on or before the {{asof_refused_cutoff}} cutoff
([`results/asof_demo_r196.json`](results/asof_demo_r196.json)). On case {{asof_served_case}}, picked by a rule fixed
before any call, it served the {{asof_served_capture}} copy, which writes no date after the {{asof_served_cutoff}}
cutoff, while the live Extract writes {{asof_served_live_n}} dates after it ({{asof_served_live_list}}; a date in
the text is not always an update)
([`results/asof_demo_served.json`](results/asof_demo_served.json)).

```python
from timelock import TavilyHTTP, extract_as_of, timelocked_search

client, cutoff = TavilyHTTP(), "2026-10-06"                     # 1 search credit + 1 Extract credit per page
results = timelocked_search(client, "RBI monetary policy repo rate decision October 2026", cutoff, topic="news",
                            max_results=3, include_published_date=True)
for r in results:
    page = extract_as_of(client, r["url"], cutoff, published_date=r.get("published_date"))
    print(r["status"], r["url"], page["provenance"])
    print((page["text"] or "no as-of copy: do not use this page")[:300])
```

- **MCP server** [`mcp/`](mcp/README.md): `timelocked_search` and `extract_as_of` as tools for Claude Code, Claude
  Desktop or any MCP client; results after the cutoff come back as domain and date only, never their text or URL.
- **Benchmark** [`benchmarks/timelock34/`](benchmarks/timelock34/DATASHEET.md): {{tl_cases}} cases,
  {{tl_questions}} distinct questions (two pairs share a question and its searches), from the date test and the
  finance check, with every result URL labelled (Wayback-confirmed leak, date flag, unknown) and a scorer for any
  search function (leak rate with Wilson intervals, valid evidence kept). New URLs a search returns are unlabelled
  until reviewed and are never counted as safe. Labels under CC BY.
- **`shadow_cpi/pit`** ([`shadow_cpi/pit/README.md`](shadow_cpi/pit/README.md)): the pipeline's wrapper around
  `timelock/`, adding the Flight Recorder and a month-start window.
- **Agent skill** [`skills/time-locked-search/SKILL.md`](skills/time-locked-search/SKILL.md): the same rules for any
  agent that searches the past.

### For research teams

Shadow CPI doesn't claim to solve temporal leakage. It makes retrieval-based backtests auditable: dates are enforced in code, every retrieval is logged and timestamped, results come with their uncertainty, and live forecasts are sealed before the official release. Not adopted by any team yet. Exports (`python tools/export.py`, columns in
[`docs/exports_schema.md`](docs/exports_schema.md)), `as_of()`, the seal checks and the leak checker
([`timelock/check.py`](timelock/check.py), example in
[`examples/leakcheck_example.py`](examples/leakcheck_example.py)). Research tool, not investment advice.

## The problem

India's official Consumer Price Index (CPI) inflation figure, published by the Ministry of Statistics and Programme
Implementation (MoSPI), arrives about {{release_lag}} days after the month ends. So anyone forecasting it from the web
has to replay past months, and a replay that quietly reads a page published after its cutoff looks better than it
could ever be live (look-ahead bias).

Shadow CPI is a Tavily-grounded India CPI nowcast that tests, rather than assumes, Tavily's date controls and measures
what they cost. El Lahib et al. ({{lahib_year}}, [arXiv {{lahib_arxiv}}](https://arxiv.org/abs/{{lahib_arxiv}})) found
at least one retrieved page containing major post-cutoff leakage for {{lahib_pct}} of Google-audited questions, after {{lahib_queries}} queries
and about {{lahib_urls}} URLs each; our {{dt_nodates}}/{{dt_cases}} on the pre-registered initial pass ({{dt_nodates_retry}}/{{dt_cases}} after the logged archive retry) is per search task, so the rates are not directly
comparable.

### Related work

{{related_position}} Related studies, each checked on its arXiv page:

{{related_work}}

## How it works

```mermaid
flowchart LR
    S["Tavily Search<br/>proposes pages, dates locked"] --> X["Tavily Extract<br/>reads the page"]
    X --> N["Nemotron on Nebius Token Factory:<br/>Nano screens the page, Super cites a numbered line;<br/>code checks the number is in it"]
    N --> C["Plain code computes<br/>(index levels x official weights)"]
    C --> SEAL["Seal: canonical JSON +<br/>SHA-256 + git tag"]
```

1. **Tavily Search proposes.** Every search carries `start_date`/`end_date`; the later time-locked searches (date
   test, radar, `timelock/`) also send `filter_by_published_date`. Code re-checks each result's date and drops
   anything after the cutoff. v1's frozen evidence search used the dates plus our page-date check only.
2. **Tavily Extract reads the page.** A snippet is a pointer, not evidence. The model returns a line number; code
   copies that line from the Extract output and checks the number is in it. A model never writes a quote.
3. **Plain code computes.** Index levels combined with MoSPI's official weights, year-on-year last. A model never
   picks a number, a range or a weight.
4. **The seal.** Canonical JSON, its `SHA-256`, and a git tag. We publish the prediction's SHA-256 and a Git tag
   before release, so anyone can verify the file they have. The seal proves when the forecast was
   committed, not what was read before it; the time lock and `extract_as_of` address the evidence.

## How we use NVIDIA Nemotron on Nebius Token Factory

Nano screens pages, Super cites the exact line, code checks the number. Nemotron Nano answers one yes/no question
per page ("does this page state an Indian price or price change?"); Nemotron Super reads the page as numbered lines
and returns the line number for each price; code copies that line from the Extract output and keeps the claim only
if the number is in it. A model never writes a quote, a number, a range or a weight. Two models, one
OpenAI-compatible endpoint ([`shadow_cpi/nemotron.py`](shadow_cpi/nemotron.py)); calls from the flight recorder
([`results/app/flight_recorder.jsonl`](results/app/flight_recorder.jsonl)):

| Model (Token Factory ID) | From {{switch_day}} (Nebius's replacement) | Job | Calls sent (including cache hits) |
|---|---|---|---|
| Nemotron Nano, `{{nano_id}}` | `{{nano_new}}` | Gatekeeper: "does this page state an Indian price or price change?" (yes/no); English glosses of non-English quotes, for display only | {{nano_sent}} ({{nano_total}}) |
| Nemotron Super, `{{super_id}}` | `{{super_new}}` | Reads pages and cites the line for each price and price change; writes the search fields in arms B, C and H | {{super_sent}} ({{super_total}}) |

**The dated model switch on {{switch_day}}.** Nebius retires the original IDs on {{switch_day}}; from then, calls
use Nebius's recommended replacements (pre-registered on {{migration_registered}}). The model is picked by the call
date in IST ([`config/models.json`](config/models.json)) and logged with every call; the {{live_month}} seal uses the
original models ([`v2/PREREGISTRATION.md`](v2/PREREGISTRATION.md), Amendment G).

**Where Token Factory helped** (each from a dated entry in [`FEEDBACK_NOTES.md`](FEEDBACK_NOTES.md)): JSON-schema
output worked on the opening call, so every model answer is parsed, not guessed; the `/models` list served both
model sizes behind the one endpoint, so the cheap gatekeeper and the careful reader are picked by name in
[`config/models.json`](config/models.json); and having Super cite line numbers instead of copying text made Hindi
pages work. The same notes log what needed work (a gatekeeper "no" on a page with rupee prices, a timeout and a
connection reset that stopped long runs, mixed model naming).

## The product

- **The {{live_month}} nowcast.** {{seal_status}}; {{live_month}} CPI is scheduled for {{release_day}} at {{release_hour}}
  IST (MoSPI's next-working-day rule applies). Anyone can check the seal: download `sealed/2026-10.json` at tag `seal-2026-10`, recompute its `SHA-256`, and
  compare it with `sealed/2026-10.sha256` ([`verify.md`](verify.md)). Sealed {{sealed_at}}: headline {{seal_headline}} year on year,
  {{seal_range_level}} range {{seal_range}}, P(≥{{seal_threshold}}) {{seal_p_ge6}}; `SHA-256` `{{seal_sha256}}`.
  The `v3` bundle was not sealed for October: its build check counted the radar's {{seal_day}} data files (`v2/radar/*.json`) as code changes; per `v3/PREREG.md §6`, `v1` stands alone. The check will be fixed (data vs code) before November.
  The seal shows when the forecast was committed;
  what the evidence could have seen is the time lock's job. After the release, the Archive page shows the
  miss and whether the official figure was inside the range.
- **Price Shock Radar** (exploratory, report only; app page "October radar"): announced retail price changes taking
  effect this month, found with Tavily before MoSPI publishes. So far {{radar_events_phrase}} verified,
  {{radar_corroborated}} corroborated, {{radar_spent}} of a {{radar_cap}}-credit cap. It never changes the sealed call.
- **Live build** with **Replay a saved run**: watch the number build one verified card at a time. Replays make no
  API call and cost no credits.
- **Chain of custody:** from any number to its quote, page, page date, Tavily request ID, response hash and seal.
- **`as_of(day)`** ([`v2/asof.py`](v2/asof.py), app page "As of a date"): the nowcast and evidence as known on a
  past day; a test proves nothing found later can appear.

## Scoreboard

{{replay_span}} replay, pre-registered, with one disclosed post-scoring correction ({{mae_c_before}} → {{mae_c}})
([`results/score_lock.json`](results/score_lock.json),
[`results/scoreboard.md`](results/scoreboard.md)); mean absolute miss in percentage points:

| Method | Mean miss |
|---|---|
| Shadow CPI v1 (replay) | **{{mae_c}}** |
| Trend only | {{mae_trend}} |
| Repeat last month's rate | {{mae_b1}} |

- On the {{poll_months}} months with an economists' poll: Shadow CPI {{mae_poll_c}}, the poll {{mae_poll}}. About a tie.
- The {{range_level}} range held the official figure in {{inside}} of {{months}} months, below its target.
- Shadow CPI v2 was not better: {{mae_v2}} ([`results/v2_score_lock.json`](results/v2_score_lock.json)).

## Honest limits

Short answers to the hardest questions: [`docs/judge_faq.md`](docs/judge_faq.md). Full list: [`docs/honest_limits.md`](docs/honest_limits.md).

- Coverage: {{cov_low}}–{{cov_high}} of the CPI basket is measured each month; the rest is assumed to follow its trend.
- Why {{dt_cases}} date-test cases and {{fin_events}} finance events: the pre-registration files say only this
  (quoted verbatim). `v2/DATE_TEST_PREREG.md`:
  > {{prereg_date_cases}}
  >
  > {{prereg_date_deviation}}

  `v2/FINANCE_PREREG.md`, in the amendment that fixed the event list before any search:
  > {{prereg_fin_count}}

  Neither file says why these sizes were chosen beyond that, and no power calculation is recorded, so both are small
  pilots; every count carries a Wilson interval.
- Web news quotes ran in full only for {{web_quotes_month}}; the other replay months used official price lists, government
  food prices and announced price-change events.
- Windows: searches start {{pre_days}} days before the month (announcements). v1's replay ran to each month's last day;
  the live seal uses evidence up to the {{cutoff_day}}, so the replay was slightly easier than live.
- v1 used `start_date`/`end_date` plus our own page-date check; `filter_by_published_date` came later (date test,
  radar, `timelock/`). v1 is frozen and was not changed.
- Recall: the winning search arm found {{arm_a_recall}} of {{known_changes}} known price changes.
- **Model memory.** The time lock controls what the search returns, not what the models already know. NVIDIA's
  model cards (checked {{cutoffs_checked}}) give Nemotron Nano a pre-training cutoff of {{nano_pre}} and a
  post-training cutoff of {{nano_post}}; Nemotron Super a pre-training cutoff of {{super_pre}} and a post-training
  cutoff of {{super_post}}, inside the {{replay_span}} replay; for the replacement models: {{new_models_cutoff}}. The replay is therefore not
  leakage-free against model memory: a model can cite a line it would not have picked without knowing the outcome,
  even though code checks that the number is on the page. The sealed forward forecasts are the clean evidence.
- **Bounds on the time-lock zero.** The count of confirmed leaks leaves out results the archive could not confirm either
  way: {{et_c_unknown}} of {{et_c_results}} time-locked results. If every case with such a result had leaked, the count
  would be {{et_c_worst}} of {{et_cases}} cases (exploratory bounding range, not a result; Field Report, "Evidence
  tiers and bounds", [`results/evidence_tiers.json`](results/evidence_tiers.json)).
- **Leak counts.** Every zero is reported as zero detected, with its Wilson interval; no-dates counts are lower bounds, because a
  leak counts only when the Wayback Machine confirms it and absence from Wayback is not proof a page did not exist.
  McNemar tests and the rule-of-three bound are {{posthoc_label}}
  ([`results/posthoc_stats.md`](results/posthoc_stats.md)).
- **Content check.** A content check (Nemotron Nano, exploratory) found {{cc_facts}} in {{cc_sampled}} sampled
  time-locked search excerpts, via a related-stories item, so {{pool_dated}} of {{pool_cases}} cases detected by our
  date-and-archive rule is a lower bound. Excerpts and cases are different units: the {{pool_cases}} cases are the pilot
  plus the replication; the {{cc_sampled}} excerpts are a sample of their saved search results
  (`docs/preregistration_content_check.md`, `results/content_check.json`).
- Small samples: pilot and exploratory checks of tens of cases, reported with Wilson intervals; exploratory results
  are labelled and changed no scored verdict. {{dt_cases}} date-test cases and {{fin_events}} finance events are small,
  India-focused samples; they show the effect exists and its size here, not Tavily's behaviour in general.
- Data vintage: MoSPI began publishing the {{base_year}}-base series (with its {{base_history_year}} history) on
  {{base_published}}. A real {{base_first_month}} nowcast could not have used that history; our {{base_first_month_short}}
  replay did. From {{base_public_from}} on, the history was public before each nowcast.
- An audited event that may have been reversed is left in: an Uttar Pradesh (UP) electricity surcharge that later
  reports say the regulator put on hold. It is inside the score ([`docs/honest_limits.md`](docs/honest_limits.md)).
- Custody: {{custody_both}} of {{custody_total}} entries have both a request_id and a response hash; they were logged
  only for the later arms (C, T, T+dates, H and the radar), and earlier runs say "not logged"
  ([`results/custody.json`](results/custody.json)).
- Direct, non-Tavily sources, each logged: the MoSPI API (official indices and weights), the Department of Consumer
  Affairs (DoCA) daily food prices (downloaded by hand from behind a CAPTCHA), and Wayback Machine lookups (date test
  only).
- Quote check of the {{q_events}} audited events (AI-assisted audit; pages then opened in a browser): {{q_verbatim}} verbatim, {{q_paywalled}} paywalled,
  {{q_not_checked}} not checked ([`audit/quote_check.md`](audit/quote_check.md)).
- We built a value-of-information score to rank searches; it rated almost every search as worthless, so we dropped it
  rather than tune it.
- A Hindi substring match ('rail' inside 'domestic') turned a Jharkhand power tariff into a 'Bihar rail' event.
  Our manual check caught it; the fix (whole-word matching, state from the page) removed the event, so the October
  radar has {{radar_events_phrase}}. Logged as rule changes `R2`–`R3`, with before and after
  ([`v2/RADAR_PREREG.md`](v2/RADAR_PREREG.md)).

More: [`docs/honest_limits.md`](docs/honest_limits.md), [`docs/frozen_rules.md`](docs/frozen_rules.md),
[`docs/after_scoring_changes.md`](docs/after_scoring_changes.md).

## Tamper-evident call log

`tools/audit_log.py <date>` turns that day's `results/credit_ledger.jsonl` and flight recorder into `results/audit_log/<date>.jsonl`: one entry per API call (time, service, endpoint, request id, query or URLs, status, credits, response SHA-256), each carrying `prev_hash` and an `entry_hash` over its canonical JSON. The final hash goes in `<date>.head`, and that file is timestamped with [OpenTimestamps](https://opentimestamps.org) (`<date>.head.ots`). `python tools/verify_audit_log.py results/audit_log/<date>.jsonl` recomputes the chain and reports OK or the earliest broken entry.

Day logs are built after the day ends (IST) and stamped with OpenTimestamps; run tools/verify_audit_log.py to check.

A "day" is an IST calendar day (Asia/Kolkata, UTC{{audit_tz_offset}}, {{audit_day_span}}), whatever time zone the machine is in. The builder refuses a day that has not ended; `--partial` writes an unstamped, uncommitted `<date>.partial.jsonl` for a look at a day in progress. Questions typed by visitors on the Try it page are logged as `visitor query` plus the SHA-256 of the text; our own pipeline queries stay readable. Nothing is capped or truncated: an entry exists for every recorder call in the day.

An earlier test stamp of {{audit_old_date}} (head {{audit_old_head}}…, {{audit_old_entries}} entries) used a {{audit_old_basis}} day; it was superseded by the IST-day log (head {{audit_head}}…, {{audit_entries}} entries) the same afternoon. Only the IST-day logs are current. The recorder keeps at most {{audit_url_cap}} URLs per extract call, so the log lists no more than that per call.

To stamp or check the `.ots` proofs: `pip install -r requirements-dev.txt` (the chain check needs nothing beyond the standard library).

**What it proves:** once the head is stamped, the log of our calls has not been altered since: editing, reordering or deleting any entry breaks the chain, and the stamp pins the head to a Bitcoin block time. The `.ots` files are *pending* until `ots upgrade <file>.ots` is run after the calendar commits to a block (hours); run that later and commit the result.

**What it does not prove:** the log is built after the fact each day from our own ledger and recorder, not at call time, so it cannot show those files were honest before the build. It records response hashes, not page text, so it does not prove what any page said. It holds metadata only (no page text, no keys).

## Run it locally

Python {{python_ci_min}} or newer (CI runs {{python_ci}}; the local suite last ran on {{python_tested}}).

```bash
git clone https://github.com/bhavikjain026/shadow-cpi.git
cd shadow-cpi
```
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```
```bash
pip install -r requirements-app.txt
```
```bash
streamlit run app.py
```

The app reads the committed results files, so it needs no keys. "Run live" stays off unless `RUN_LIVE_ENABLED` is set
and both keys (`SCPI_TAVILY_API_KEY`, `SCPI_NEBIUS_API_KEY`) are in the environment. Tests (no keys, no credits):

```bash
python -m pytest -q
```

To run the pipeline, copy `.env.example` to `.env`, add the two keys, and start with `python checks.py`. Deployment:
[`docs/deploy.md`](docs/deploy.md). Every number in this README is filled from the results files by
`python tools/sync_doc_numbers.py` (template: [`docs/templates/README.md`](docs/templates/README.md)).

Tavily usage so far (as of {{as_of}}, [`results/tavily_report_card.md`](results/tavily_report_card.md)):
{{run_calls}} calls sent, {{run_credits}} credits used (a {{plan_limit}}-credit monthly plan plus {{addon_credits}}
add-on credits), {{run_inside_pct}} of dated search results inside the requested window, median latency
{{run_latency}}.

## Licence, team, and when it was built

MIT ([`LICENSE`](LICENSE)). Third-party libraries, data sources and quoted excerpts:
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Built for the Nebius × NVIDIA Global AI Hackathon.

Team: [TBD]

Newly created during the submission period (opened {{submission_opened}}); first commit {{earliest_commit}}.
