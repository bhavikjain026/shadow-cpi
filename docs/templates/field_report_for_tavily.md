# Field report for Tavily's engineers

Shadow CPI, built for the Best Use of Tavily prize. Numbers read from the committed results files by
`python tools/sync_doc_numbers.py` (as of {{as_of}}); edit `docs/templates/field_report_for_tavily.md`, not this file.
Conflict of interest: this hackathon is hosted by Nebius, which owns Tavily; see the README.

## The headline measurement
- With `start_date`/`end_date` and `filter_by_published_date`, {{pool_dated}} of {{pool_cases}} cases detected leaking (Wilson {{pool_dated_w}}); pre-registered pilot plus replication.
- With no dates, {{pool_nodates}} of {{pool_cases}} (Wilson {{pool_nodates_w}}); a lower bound, because a leak counts only when the Wayback Machine confirms it.
- The zero is not proof of no leak: the archive confirmed {{et_c_archived}} of {{et_c_results}} time-locked results as published before the cutoff, {{et_c_unknown}} could not be checked, and a content check found {{cc_facts}} in {{cc_sampled}} sampled excerpts (exploratory).

## Three questions, Tavily answers two
1. **Which pages?** Dates choose pages: `start_date`/`end_date` select by `published_date`, and {{autod_inside}} of {{autod_dated}} dated results fell inside the window we sent. Answered.
2. **How old is the cached copy?** `max_age_hours` is cache age, a freshness bound. Answered.
3. **Which version of the page existed on the cutoff date?** Nobody answers this. `{{ex_row}}` ({{ex_company}} results preview) was dated {{ex_published}}, before its {{ex_cutoff}} cutoff, and updated on {{ex_updated}} with a link to the actual result; Extract returns the updated page. The content check found the same thing inside a page that passed the filter: a related-stories item dated after the cutoff (`results/content_check_labels.json`). `extract_as_of` fills the gap from archives in our code (demo, n={{asof_n}}; `results/asof_demo_r196.json`).

## Field notes
Each note has observed / expected / suggested change, request IDs and a one-request repro script: `docs/tavily_bug_reports.md`. Verdicts say what showed on the re-check date only; the original measurements stand as measured.

| # | Note | Tag against the docs | Re-checked {{recheck_date}} | Repro script |
|---|---|---|---|---|
{{fr_notes_table}}

## Three feature requests
1. **Say where `published_date` comes from and how confident it is.** The documented definition is published or last updated (beta). It was later than the page's own date on {{pd_later}} of {{pd_pages}} distinct pages, and a caller cannot tell which kind of date a result carries. Suggested: a source field (page metadata, sitemap, initial crawl) and a confidence value. Evidence: `results/date_field_test.json`.
2. **An as-of / snapshot mode for Extract and Search excerpts.** Return the copy as it was on a given date, or at least the crawl time of the copy returned. Dates select pages, not versions, and `max_age_hours` does not reflect a date. Evidence: `results/timelock34_second_review.json` (`{{ex_row}}`; request ID in `docs/tavily_bug_reports.md`) and `results/asof_demo_r196.json`.
3. **Date parameters on `/research`.** The request body has no date parameter (checked {{research_checked}} in the API reference), so a research call cannot be time-locked the way Search can; we do not use it for dated work for that reason. Evidence: the parameter list recorded in `config/doc_citations.json` (`tavily_research_params`). Not measured.

## Reproduce
`repro/README.md`: one request per note, your own key, at most a few credits each. Every API call is logged in a hash-chained log (`results/audit_log/`).
