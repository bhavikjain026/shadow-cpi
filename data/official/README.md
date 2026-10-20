# MoSPI's official files (2024-base CPI)

| File | What it is | How it got here |
| --- | --- | --- |
| `mospi_cpi2024_weights_Annex_5.3.xlsx` | 2024-series weights: divisions (5.3a), groups (5.3b), states (5.3c), items by state and sector (5.3d) | Downloaded earlier (Expert Group report annex) |
| `mospi_cpi2024_expert_group_report.pdf` | The Expert Group report the weights come from | Downloaded earlier |
| `mospi_api/cpi2024_allindia_combined_<YYYY-MM>_p<N>.json` | All-India **Combined** indices, Jan 2025 – Sep 2026, every level (CPI General, divisions, groups, classes, sub-classes, 358 items), 7 pages a month | `python build_official.py` – MoSPI's public CPI API (`api.mospi.gov.in/api/cpi/getCPIData`, `base_year=2024`), fetched as the logged direct-download route (Flight Recorder service `direct`, tag `official-mospi-api`) |
| `mospi_api/cpi2012_allindia_combined_2025-12.json` | December 2025 on the old 2012 base | Used only for B1's January 2026 input (the last print before the new series). No 2012 weights are used anywhere. |

Food and beverages weight in the 2024 series: **36.753%** (2012 series: 45.86%). `build_official.py` refuses to run otherwise.

Economists' polls are in `data/poll.csv` (found with Tavily by `python find_polls.py --go`).
