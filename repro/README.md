# Reproduce the Tavily feedback

One short script per Tavily item in [`docs/tavily_bug_reports.md`](../docs/tavily_bug_reports.md). Each sends one
request with your own key, prints Tavily's `request_id` and the credits it reports, and costs at most 2 credits.
Standard library only; the key is read from the environment and never printed or written.

```bash
export TAVILY_API_KEY=...        # your own key
python repro/auto_parameters_time_range.py
```

| Script | Item | Credits |
| --- | --- | --- |
| [`auto_parameters_time_range.py`](auto_parameters_time_range.py) | auto_parameters picks a recent time_range | 2 |
| [`auto_parameters_echo_dates.py`](auto_parameters_echo_dates.py) | echo shows time_range, not our dates | 2 |
| [`extract_no_asof.py`](extract_no_asof.py) | Extract has no as-of view | 1 |
| [`published_vs_modified.py`](published_vs_modified.py) | published vs last-modified date | 1 |
| [`map_empty.py`](map_empty.py) | Map returns empty results silently | 2 |
| [`scanned_pdf_extract.py`](scanned_pdf_extract.py) | scanned PDF returns the letterhead only | 1 |
| [`usage_lag.py`](usage_lag.py) | /usage lags per-call usage | 1 |

Pages and Tavily's index change, so the output may differ from ours. The scripts print what they see and never
assume an expected count. A script refuses before sending if its estimate is above 2 credits.
