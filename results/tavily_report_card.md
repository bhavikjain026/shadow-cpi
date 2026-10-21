# Tavily report card

Computed by `tools/prompt_t.py card` from `logs/flight_recorder.jsonl`, `results/credit_ledger.jsonl` and the manifests on 2026-10-21. Credits are Tavily's own per-call `include_usage` counts (the `/usage` endpoint did not update; see FEEDBACK_NOTES.md).

| Measure | Value |
| --- | --- |
| Tavily calls sent (uncached) | 775 (plus 4362 served from the cache) |
| Credits used (ledger + 160 before it) | 684 of 1500 |
| Credits per replay prediction (events + skeptic, mean of 9 months) | 40.3 |
| Search results inside the requested date window | 1952 of 2535 (77%); 577 undated |
| Price quotes verified word-for-word (Prompt 2 March run, manifest at f00bd45) | 91 of 93 (98%) |
| Events confirmed by 2 sources (replay months) | 3 of 12 |
| Events with a confirming result from evidence chasing | 5 of 12 |
| Median latency, uncached calls | 4.3 s |
| Direct downloads (logged; MoSPI API, DoCA by hand, failed Extracts) | 154 uncached calls |

## Official sites (Map + Crawl)

**2026-10** (instructions: "find price circulars or tariff orders published in October 2026")

- merc (https://merc.gov.in): map 0 addresses, crawl 0 pages (0 failed), 0 mention the month, 0 verified price events
  - fallback (site search "tariff order 2026", then Crawl depth 1): 4 addresses found; crawl from https://merc.gov.in/wp-content/uploads/2026/03/Order-in-Case-No.1-SM-2026.pdf read 0 pages, 0 mention the month, 0 verified events
- derc (https://www.derc.gov.in): map 0 addresses, crawl 1 pages (0 failed), 0 mention the month, 0 verified price events
- uperc (https://www.uperc.org): map 0 addresses, crawl 0 pages (0 failed), 0 mention the month, 0 verified price events
  - fallback (site search "tariff order 2026", then Crawl depth 1): 5 addresses found; crawl from https://www.uperc.org/App_File/UPPTCL_TariffOrder_26_27_DigitallySigned-pdf415202652122PM.pdf read 0 pages, 0 mention the month, 0 verified events
- iocl (https://iocl.com): map 0 addresses, crawl 0 pages (0 failed), 0 mention the month, 0 verified price events
  - fallback (site search "petrol diesel LPG price", then Crawl depth 1): 5 addresses found; crawl from https://iocl.com/petrol-diesel-price read 0 pages, 0 mention the month, 0 verified events
- amul (https://amul.com): map 0 addresses, crawl 0 pages (0 failed), 0 mention the month, 0 verified price events
  - fallback (site search "milk price", then Crawl depth 1): 5 addresses found; crawl from https://shop.amul.com/en/browse/milk read 10 pages, 0 mention the month, 0 verified events

## Honest notes

- Map + Crawl results are reported, not used in the nowcast: the frozen event layer searches news only.
- Evidence chasing ran on the 9 scored months after scoring; it does not change any scored number.
- Map returned 0 addresses on all four government/PSU sites (merc.gov.in, derc.gov.in, uperc.org, iocl.com) with no error and 0 credits; only amul.com mapped (17 addresses, all marketing pages). Crawl from a section page found by a site search read 0 pages when that page was a PDF.
- DERC's tariff-order index was read: its newest order is dated 31/12/2025, so nothing for October 2026.
- A chase "confirmation" is a code text match (another site names the item and states the same amount or %), not a Nemotron-verified quote. Spot check: 13 of 14 confirming results are the same change; 1 is a generic all-India milk article.
- Failed sources are listed on the Evidence page and in FEEDBACK_NOTES.md (Reuters, JavaScript data portals, the Consumer Affairs price site).
