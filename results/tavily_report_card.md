# Tavily report card

Computed by `tools/prompt_t.py card` from `logs/flight_recorder.jsonl`, `results/credit_ledger.jsonl` and the manifests on 2026-10-21. Credits are Tavily's own per-call `include_usage` counts (the `/usage` endpoint did not update; see FEEDBACK_NOTES.md).

| Measure | Value |
| --- | --- |
| Tavily calls sent (uncached) | 788 (plus 6845 served from the cache) |
| Credits used (ledger + 160 before it) | 694 of 1500 |
| Credits per replay prediction (events + skeptic, mean of 9 months) | 40.3 |
| Search results inside the requested date window | 1952 of 2535 (77%); 577 undated |
| Price quotes verified word-for-word (Prompt 2 March run, manifest at f00bd45) | 91 of 93 (98%) |
| Events confirmed by 2 sources (replay months) | 4 of 9 |
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

## Dairy sites (Map + Extract, 2026-10-21, report only)

| Dairy | Site | Map addresses | Price-looking pages extracted | Years on those pages |
| --- | --- | --- | --- | --- |
| amul | https://amul.com (2) | 2 | 1 | – |
| mother-dairy | https://www.motherdairy.com (30) | 30 | 2 | 2024, 2025 |
| aavin | https://aavin.tn.gov.in (0); https://aavinmilk.com (0) | 0 | 0 | – |
| nandini-kmf | https://www.kmfnandini.coop (0) | 0 | 0 | – |
| sanchi-mpcdf | https://www.mpcdf.nic.in (ApiError: HTTP 400: {"detail":{"error":"…); https://www.sanchi.co.in (ApiError: HTTP 400: {"detail":{"error":"…) | 0 | 0 | – |
| gokul | https://www.gokulmilk.coop (3) | 3 | 3 | 2026 |
| sanchi-indore (MPCDF union) | https://www.sanchiindore.com (0) | 0 | 0 | – |

Test-month milk events stated (same amount and month) on the dairy's own extracted pages: **0 of 6**.

- Mother Dairy: the press page lists milk price rises up to 3 June 2024 (+₹2/litre) and press PDFs to 10.09.2025; no 2026 release was among the 30 mapped addresses (the map limit), so the May 2026 Amul/Mother Dairy ₹2 rise was not found on its own site.
- Gokul: the map found milk_rates_english_wef_11_08_2026.pdf, a rate list effective 11 Aug 2026, the same date as the August 2026 Maharashtra ₹2 rise. The PDF's rates are not readable as text (basic and advanced Extract both returned only the letterhead), so the amount cannot be checked; the date match comes from the file name only.
- Amul mapped 2 addresses (media pages); the media page loads its news by script and returned no items.
- Aavin (aavin.tn.gov.in, aavinmilk.com), Nandini (kmfnandini.coop) and Sanchi Indore (sanchiindore.com) mapped 0 addresses, no error, 0 credits. mpcdf.nic.in and sanchi.co.in were rejected as 'Invalid Start URL'.
- Credits for this step: 10 of its 30 cap (Mother Dairy map 6, Amul map 1, extracts 1, Gokul advanced extract 1, Sanchi site search 1).

## Honest notes

- Map + Crawl results are reported, not used in the nowcast: the frozen event layer searches news only.
- Evidence chasing ran on the 9 scored months after scoring; it does not change any scored number.
- Map returned 0 addresses on all four government/PSU sites (merc.gov.in, derc.gov.in, uperc.org, iocl.com) with no error and 0 credits; only amul.com mapped (17 addresses, all marketing pages). Crawl from a section page found by a site search read 0 pages when that page was a PDF.
- DERC's tariff-order index was read: its newest order is dated 31/12/2025, so nothing for October 2026.
- A chase "confirmation" is a code text match (another site names the item and states the same amount or %), not a Nemotron-verified quote. Spot check: 13 of 14 confirming results are the same change; 1 is a generic all-India milk article.
- Failed sources are listed on the Evidence page and in FEEDBACK_NOTES.md (Reuters, JavaScript data portals, the Consumer Affairs price site).
