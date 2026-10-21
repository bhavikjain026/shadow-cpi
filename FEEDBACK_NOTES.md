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
