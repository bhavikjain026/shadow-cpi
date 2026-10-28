# Gallery

Four images for the Devpost gallery (`1600x900` each). The two app shots and both diagrams are drawn by
`python tools/build_gallery.py --app <app URL>`; these captions are filled from the results files by
`python tools/sync_doc_numbers.py` (edit `docs/templates/gallery.md`, not this file).

## The opening screen
![Leak demo, the app's opening screen: no time lock vs Tavily's time lock, date test](1_leak_demo.png)

**Can a search engine keep the past in the past?** The app's opening screen. Date test (pilot, {{dt_cases}} past
cases, the pre-registered initial pass): with no dates, {{dt_nodates}} of {{dt_cases}} cases kept a confirmed leak, a
page dated after the cutoff with no archive copy on or before it (Wilson {{wilson}} {{dt_nodates_w}};
{{dt_nodates_retry}} of {{dt_cases}} after retrying the {{rr_dt_failed}} archive lookups that had failed); with
`start_date`/`end_date` and `filter_by_published_date`, {{dt_dated}} of {{dt_cases}} ({{dt_dated_w}}). The cost: the
filter dropped {{dt_lost_filter}} of {{dt_valid_total}} pieces of valid evidence (initial pass). Replication
(pre-registered, {{rep_cases}} new cases, initial pass): no dates {{rep_nodates}} of {{rep_cases}}, dates + filter
{{rep_dated}} of {{rep_cases}} ({{rep_dated_w}}); pilot and replication together, same rule: {{pool_dated}} of
{{pool_cases}} with dates + filter ({{pool_dated_w}}). Red card: no time
lock; green card: Tavily's time lock. App page: Leak demo (home). Source: `results/leak_demo.json`,
`results/field_report.json`, `results/replication.json`.

## The four-arm table
![Field Report: who should write the search, four arms](2_four_arm_table.png)

**Who should write the search?** On {{known_changes}} known price changes, fixed code templates (arm A) found
{{arm_a_recall}}; Nemotron-written fields (arms B and C) {{arm_b_recall}} and {{arm_c_recall}}; Tavily
`auto_parameters` (arm T) {{arm_t_recall}}. The model's fields were always valid ({{bc_fields_valid}} of
{{bc_fields}}), but templates found more, so the model may choose words and sources while code owns the dates.
Pre-registered. App page: Field Report. Source: `results/field_report.json`, `results/v2_ablation.json`.

## {{asof_row}}: a search date does not freeze the page
![{{asof_row}} timeline: Tavily date, cutoff, page edited, extract_as_of refuses](3_r196_timeline.png)

**{{asof_row}}**, a {{ex_company}} results preview: Tavily dated it {{asof_tavily}}, the cutoff was {{asof_cutoff}},
and the page was edited {{asof_page}} with a link to the actual result, so Extract today returns the edited page.
`extract_as_of` looks for an archived copy from on or before the cutoff; the earliest capture is {{asof_first}}, so it
returns **{{asof_reason}}** instead of today's text. A {{asof_label}} ({{asof_credits}} Tavily credit). Source:
`results/asof_demo_r196.json`.

## From search to seal
![Flow: Tavily search, time lock, Extract, quote check on page, seal](4_flow.png)

**The pipeline.** Tavily Search proposes dated pages; the time lock sends the dates and code re-checks each one;
Extract returns the page as numbered lines; Nemotron cites a line and code checks the number is in it; the
forecast is sealed with its SHA-256 and a git tag before the official release. Details: `docs/pipeline.md`.
