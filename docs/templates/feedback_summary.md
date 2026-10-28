## Summary

One row per entry, nothing new: the filed notes come from [`docs/tavily_bug_reports.md`](docs/tavily_bug_reports.md),
the Tavily field notes / repro kit (rows filled from [`results/bug_reports.json`](results/bug_reports.json), the file
those notes are built from), each tagged "documented behaviour", "doc gap" or "unexplained" against Tavily's docs;
"Not filed" rows are dated entries below that have no field note. Details and dates are in the entries.

| Priority | Product | What happens | Evidence (file or request ID) | Suggested fix |
|---|---|---|---|---|
{{feedback_summary_rows}}
| Not filed | Tavily | Research: the request body has no date window, so it cannot be time-locked (checked in the API reference, not measured) | `config/doc_citations.json` (`tavily_research_params`) | accept the same `start_date`/`end_date` as Search |
| Not filed | Tavily | Search with `language` and the date filter: the dates held, but in Marathi and Tamil fewer results named the item, and Tamil returned English pages (post-hoc) | `results/lang_date_test.json` | when few matches remain in the requested language, return fewer results or say so |
| Not filed | Tavily | Search: confirmed leaks were ordinary articles, and all came from searches sent without a date window (exploratory) | `results/field_report.json` (`leak_by_source_type`) | say in the Search docs that the date parameters keep later articles out; consider a page-type field |
| Not filed | Nebius / NVIDIA (Nemotron Nano) | The gatekeeper answered "no" for a page that plainly stated Indian rupee prices | flight-recorder id `0d914036e4ee` | none in the entry; our code now never skips a page with a visible rupee price |
| Not filed | Nebius / NVIDIA (Nemotron Super) | Extraction labelled the item from context, not from the cited line | `data/evidence/2026-03_trace.json` | none in the entry; our code requires the item name in the cited line |
| Not filed | Nebius Token Factory | A call timed out and stopped a run; our helper did not retry socket read timeouts | `results/feedback_evidence/nebius_timeout_2026-10-20.txt` | none in the entry; our helper now retries read timeouts |
| Not filed | Nebius Token Factory | A connection reset stopped a long run; our helper does not retry a reset | `logs/v2_ablation_Td_crash1.txt` (kept locally) | none in the entry |
