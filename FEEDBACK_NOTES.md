# Feedback notes: Nebius Token Factory, Nemotron, Tavily

A dated log of real friction and good points met while building Shadow CPI. Every entry points to evidence in this
repository: a flight-recorder call id (`logs/flight_recorder.jsonl`, kept locally; the cached request/response is in
`cache/`), or a committed file. Nothing here is from memory or general opinion. Add new entries at the bottom.

Flight-recorder ids below are the `id` field of a log line.

## Nebius Token Factory / Nemotron

**2026-10-20 · Good: JSON-schema output worked first time.** `checks.py` asked the small model for a strict
JSON-schema answer and got `{"ok": true, "n": 3}`. Evidence: `results/feedback_evidence/checks_report_2026-10-20.txt` line "[PASS] Nemotron JSON output";
model roles saved in `config/models.json`.

**2026-10-20 · Observation: five Nemotron models listed, with mixed naming.** The `/models` list returned
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/Nemotron-3.5-Super-VL`,
`nvidia/Nemotron-3_5-Lightning`, `nvidia/nemotron-3-super-120b-a12b` (mixed case, `3.5` vs `3_5`). Our code picks
roles by substring (`checks.py: pick`), so the naming did not break anything, but it took care to avoid choosing the
vision (VL) model for text. Evidence: `results/feedback_evidence/checks_report_2026-10-20.txt` line "Nemotron models on Token Factory"; `config/models.json`.

**2026-10-20 · Good: Hindi pages work when the model cites line numbers instead of copying text.** On the March 2026
test, 59 of 62 Hindi quotes (95.2%) passed the code check "the claimed number is in the cited line", against 117 of
117 English quotes (100%). Of the 3 Hindi failures, 2 were prices written in words ("पांच से साढ़े सात", five to
seven-and-a-half) that code cannot verify as numerals, and 1 cited no line. After all filters, 14.5% of Hindi quotes
were kept vs 12.0% of English. Evidence: `data/evidence/2026-03_trace.json` (verdicts by language);
`manifests/2026-03.json` (`detail.quote_stats.by_lang`, `detail.prev_month_quote_stats.by_lang`).

**2026-10-20 · Friction: the small model (gatekeeper) said "no" to a page that plainly had Indian prices.**
`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, asked "Does this page state a price in India (in rupees)...?", answered
`{"answer": "no"}` for the Economic Times "Delhi vegetable price today, 13/03/2026" page ("Big Onions ... retail
prices capping at ₹33 per kg"). We added a code backstop: a page with a visible rupee price is never skipped.
Evidence: flight-recorder id `0d914036e4ee` (tag `p2-gate-2026-03`); `shadow_cpi/evidence.py` (`RUPEE_PRICE`,
`gatekeeper`).

**2026-10-20 · Friction: the extraction model labels the item from context, not from the cited line.** In March,
`nvidia/nemotron-3-super-120b-a12b` returned `item: "Onion"` for a line about potatoes ("Potatoes in Mumbai and Navi
Mumbai, which were selling at around ₹20–26 per kg"), and gave the lower end of price ranges ("25 से 30 रुपये" → 25)
and the old price in "from Rs 853 to Rs 913" sentences in some cases. All are now handled in code (item name must be
in the cited line; ranges → midpoint; "from X to Y" is a change). Evidence: `data/evidence/2026-03_trace.json`
(verdict "different item (item not named in the cited line)"); tests in `tests/test_evidence.py`.

**2026-10-20 · Observation: latency.** 340 uncached Nemotron calls: median 1,677 ms, slowest 14,387 ms. No run
stopped on a Nebius error. We cannot say whether any 429 or 5xx happened: `shadow_cpi/http.py` retries those silently
and the flight recorder logs only completed calls (to do: log retries). Evidence: `latency_ms` of
`service: "nebius"` lines in `logs/flight_recorder.jsonl` (cached calls excluded).

## Tavily

**2026-10-20 · Good: dated news search plus page-address dates kept results inside the month.** The March 2026
checks returned results inside the window for English (7 of 7), strict date filter (7 of 7) and Hindi (9 of 10,
1 undated). Evidence: `results/feedback_evidence/checks_report_2026-10-20.txt` lines "Tavily news search, March 2026 window ...".

**2026-10-20 · Good: Extract reads MoSPI and IBJA PDFs.** The September 2026 MoSPI press-release PDF was read in full
(the 5.54% headline found), and IBJA daily bullion-report PDFs gave 179 trading days of gold and silver rates.
Evidence: flight-recorder id `e2752c0e8610` (tag `check-pdf`); `data/evidence/ibja_daily.json`.

**2026-10-20 · Friction: Extract cannot read reuters.com.** Every Reuters article we tried came back in
`failed_results`; the poll medians had to come from Search passages instead. Evidence: flight-recorder ids
`7ffa739997c5`, `4d43b3880b46`, `bb0eedc117c8` (tag `poll-…`, `n_failed: 4`, `n_results: 0`); `data/poll.csv`
(`evidence_from` column).

**2026-10-20 · Friction: an Extract call where every URL failed was still charged 1 credit.** 14 Extract calls
returned `n_results: 0` with all URLs failed but `usage.credits: 1` (Reuters, IBJA holiday dates, IOCL, PPAC
archive pages, data.gov.in / CEDA / India Data Portal). Evidence: flight-recorder ids `7ffa739997c5`,
`180135a378bd`, `85b457cc1b31`, `06a34a62869b`, `c39786c1cf2e` (and others with `n_results: 0`, `credits: 1`).

**2026-10-20 · Good: small successful Extract calls reported 0 credits.** Several 1-URL Extract calls that
succeeded reported `usage.credits: 0`. Evidence: flight-recorder ids `e2752c0e8610`, `7778ee7d7b62`, `3230d82cc191`.

**2026-10-20 · Friction: the Consumer Affairs price site does not work with Tavily Extract.** Extract on
`fcainfoweb.nic.in/Reports/DB/DBprices_W.aspx` failed after 27 s; the logged direct download got the page. (Its
report menu also has a CAPTCHA, so the spine is downloaded by hand.) Evidence: flight-recorder ids `d33700c7f687`
(Tavily, `n_failed: 1`, 27,307 ms) and `afa7fe7787a2` (service `direct`).

**2026-10-20 · Friction: JavaScript-rendered data pages return nothing.** Extract failed on the data.gov.in catalog
page, the CEDA food-prices portal and an India Data Portal page; ibjarates.com returned its terms page but no rates
(they load by script). Evidence: flight-recorder id `c39786c1cf2e`; the `explore-gold` extract of
`https://www.ibjarates.com` in the cache.

**2026-10-20 · Friction: the `/usage` endpoint did not update all day.** It reported `plan_usage: 6` of 1,500 at
every check on 2026-10-20, while Tavily's own per-call `include_usage` counts added up to 226 credits by 16:36 UTC.
We budget from `include_usage` (our ledger) instead. Evidence: `results/feedback_evidence/tavily_usage_2026-10-20.json`
(the endpoint's response next to the flight-recorder and ledger totals); `results/credit_ledger.jsonl`.

**2026-10-20 · Friction: `include_domains_mode="prefer"` still let many off-target results through.** The poll
searches for India's CPI returned Reuters polls on the euro zone, US, Japan, Korea and Argentina; a stricter parser
and a `restrict` query were needed. Evidence: cached search responses for tags `poll-2026-01` … `poll-2026-09`;
`shadow_cpi/polls.py` (`about_india`, tiered `poll_line`).

**2026-10-20 · Friction: a Nemotron call timed out after 180 s and stopped a run.** During the August 2026 replay, a
`price_events` call to `nvidia/nemotron-3-super-120b-a12b` raised `TimeoutError: The read operation timed out`. Our
HTTP helper retried HTTP errors but not socket read timeouts, so the run stopped; it now retries those too
(`shadow_cpi/http.py`). Evidence: `results/feedback_evidence/nebius_timeout_2026-10-20.txt` (the run log with the
traceback).

**2026-10-21 · Friction: Map returned nothing on four Indian government/PSU sites, with no error.** `map` on
merc.gov.in, derc.gov.in, uperc.org and iocl.com came back with `results: []`, no `failed_results` and no error, both
with `instructions` ("find price circulars or tariff orders published in October 2026") and without them. amul.com
mapped only without instructions (17 addresses, all marketing pages). An empty answer cannot be told apart from
"blocked" or "nothing matches". Evidence: flight-recorder ids `cca735af4fc0`, `00b30f479f20`, `80e04e793423`,
`7a91ecaea5f5`, `e1acf87a899e` (with instructions), `269aae09a91d`, `e14078eda563`, `5d2cde687d1e`, `1094935388de`
(without), `46e0db39081f` (amul, 17); `results/prompt_t/official_crawl_2026-10.json`, `results/prompt_t/map_noinstr.json`.

**2026-10-21 · Friction: Crawl read 0 pages when started from a PDF or from IOCL's price page.** Crawls started at a
regulator's tariff-order PDF (MERC, UPERC) and at `iocl.com/petrol-diesel-price` returned `results: []`, although
Extract reads IOCL's LPG price page and PDFs elsewhere. Evidence: flight-recorder ids `5d37b3f5b49a`, `41b77603f9f5`,
`43cec8d2e014`.

**2026-10-21 · Good: Crawl read DERC's tariff-order table.** The one page Crawl returned from derc.gov.in was its
tariff-order index, with dates and PDF links readable as a table (newest order 31/12/2025). It did not follow the
pager links (limit 15, depth 2), so only page 1 of 14 came back. Evidence: flight-recorder id `c5be0cd02839`.

**2026-10-21 · Good: empty Map/Crawl calls were not charged.** All 16 Map/Crawl calls that returned nothing reported
`usage.credits: 0`; the one Map with results (17 addresses) cost 1 credit, the 10-page Amul crawl 1, and the 1-page
DERC crawl 0. Compare the Extract entry
above, where an all-failed call was still charged 1 credit. Evidence: `results/credit_ledger.jsonl` (budget
`prompt-t`, 2026-10-21) and the ids above.

**2026-10-21 · Friction (ours, noted for honesty): a loose text match over-counts evidence chasing.** Matching a
bare number ("2", "5") plus the item word "confirmed" all 12 events, mostly with unrelated pages (Staten Island
Railway, a New Zealand dairy result). Requiring the unit (₹/Rs/रुपये, %/फीसदी), an India marker and a different site
left 5 of 12, with 13 of 14 confirming results being the same change on a spot check. Evidence:
`results/prompt_t/chase.json` (strict rule, re-run from cache at 0 credits); `tools/prompt_t.py` (`confirms`).

**2026-10-21 · Friction: Map found nothing on 3 of 6 dairy sites, again with no error.** With instructions aimed at
price, rate, circular and press pages, Map returned `results: []` and 0 credits for Aavin (aavin.tn.gov.in and
aavinmilk.com), Nandini (kmfnandini.coop) and Sanchi Indore (sanchiindore.com). Amul gave 2 addresses, Gokul 3, and
Mother Dairy 30 (the limit). Evidence: flight-recorder ids `021473fbad42`, `7d3f5f4b3951`, `4a34a5dafb35`,
`6405e58bd72f` (empty), `f654295a4337`, `339fb8e7a9a9`, `f30499cefcd7`; `results/prompt_t/dairy_map_2026-10-21.json`.

**2026-10-21 · Good: a bad start address gets a clear error.** Map on mpcdf.nic.in and sanchi.co.in returned HTTP 400
"Invalid Start URL" at once, unlike the silent empty results above. (Our recorder logs only completed calls, so
these two are in `results/prompt_t/dairy_map_2026-10-21.json`, `tried[].error`, not in the flight recorder.) A
1-credit site search then found Sanchi's per-union sites (id `ffa240ae4a54`).

**2026-10-21 · Friction: Map's `limit` cut off the newest pages.** Mother Dairy's 30 addresses (6 credits, the most
expensive call of the step) were mostly 2023–2025 press-release PDFs, apparently in no date order; no 2026 release was
in the list, so the May 2026 milk rise could not be checked on the dairy's own site. Evidence: flight-recorder id
`f30499cefcd7`; `cache/dairy_map_2026-10-21.json` (the dated URL snapshot, kept locally).

**2026-10-21 · Friction: Extract returned only the letterhead of a dairy rate-list PDF.** Gokul's
`milk_rates_english_wef_11_08_2026.pdf` (effective 11 Aug 2026, the date of a scored Maharashtra milk event) came
back as 607 characters of letterhead with basic and with advanced Extract; the rates themselves are not readable as
text. The advanced call cost 1 credit. Evidence: flight-recorder ids `a8ce5681fcf2` (basic), `633dd10b693e` (advanced).

**2026-10-22 · Friction: auto_parameters with no dates chose time_range=w.** In our pre-registered arm T
(`v2/PREREGISTRATION.md`, Amendment F), 72 searches sent only `query`, `auto_parameters: true` and `max_results`.
auto_parameters with no dates chose recent windows, not always "w": `time_range` w 57, d 14, m 1 of 72 searches
(topic news in 71; advanced depth in 49, basic in 23). 620 of 659 results were dated October 2026, 1 September 2026
and 38 undated, and 0 of
29 known Jan–Sep 2026 changes were found. (Corrected 2026-10-22 from "w, news and advanced every time"; counted from
the arm files.) A historical, time-locked search needs explicit
`start_date`/`end_date`. Suggestion: document this, or let auto_parameters respect a supplied date window.
Evidence: `v2/ablation/arm_T_*.json` (`auto_parameters` logged per call), e.g. flight-recorder id `40f11f00fa88`, Tavily
request_id `75b29575-d839-49e2-a1b1-76fd7ee28a9b`.

**2026-10-22 · Friction: one Token Factory connection reset stopped a long run.** During the exploratory T+dates
arm, a `price_events` call to `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` raised `ConnectionResetError: [Errno 54]
Connection reset by peer` while reading the response; our HTTP helper does not retry a reset, so the run stopped
mid-January and was restarted from the cache. Evidence: `logs/v2_ablation_Td_crash1.txt` (kept locally; the
traceback).

**2026-10-22 · Friction: auto_parameters reports a time_range that the explicit dates appear to override; confusing
in traces.** In the exploratory T+dates arm (same queries as arm T, plus our `start_date`/`end_date`), the
`auto_parameters` echo still said `time_range` w 47, d 8, y 1 over 56 searches, yet 532 of 532 dated results fell
inside the supplied window. So the dates seem to win, but the logged time_range says otherwise. Suggestion: echo the
window actually applied, or drop time_range from the echo when dates are sent. Evidence: `v2/ablation/arm_Td_*.json`
(`plan[].auto_parameters`, `plan[].dates_kept`); `results/date_field_test.md` (addendum).
