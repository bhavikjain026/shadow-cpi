# Honest limits

Shadow CPI is an **experimental nowcast**. It is not an official statistic, and it does not rebuild MoSPI's survey. These are its limits, stated plainly.

## Data we could not get the "proper" way
- **Government food prices are downloaded by hand from behind a CAPTCHA.** The Department of Consumer Affairs (DoCA) report menu (fcainfoweb.nic.in) sits behind a CAPTCHA, which software must not solve, and the site blocks Tavily. `tools/fetch_doca.py` fills in the form in a visible browser and waits; a person types the CAPTCHA. Raw responses are saved in `data/official/doca/raw/` and logged as manual-captcha direct downloads. So the strictest evidence tier does not come in through Tavily, and it is not automatic.
- **Three direct sources, not Tavily**, each logged as a direct download: the Ministry of Statistics and Programme Implementation (MoSPI) API (official indices and weights), the DoCA CAPTCHA download above, and Wayback Machine CDX lookups (used only by the date test, to date pages independently).
- **Web news quotes ran in full only for March 2026.** The other replay months used the India Bullion and Jewellers Association (IBJA), Indian Oil Corporation (IOCL) and Petroleum Planning & Analysis Cell (PPAC) prices read with Tavily Extract, DoCA food prices (manual CAPTCHA download) and announced price-change events.
- **DoCA prices are zone-level, not city-level.** DoCA has published only state and national prices since September 2023; the finest monthly report is by zone (5 zones). The all-India rows we add are a simple, unweighted mean of the zones. The report has no day counts (`n_days` is blank). Rice is not taken from DoCA: its 2025 fit to MoSPI's rice index was too weak (R² 0.03), so rice is assumed to follow its recent trend.
- **Tavily is blocked on some sites.** Some government and publisher pages refuse Tavily or return no text, for example, on one scanned dairy rate-list PDF, Extract returned the letterhead but not the image-only rates. The Evidence page and the Tavily report card list every failed source openly. Where we fell back to a direct download, the report card counts it.
- **MoSPI's official indices come from MoSPI's public API** by a logged direct download (flight recorder service `direct`, raw files in `data/official/mospi_api/`). They are not fetched through Tavily, because Tavily cannot call a paged JSON API.
- **IBJA, IOCL and PPAC come in through Tavily Extract**, not direct downloads: IBJA's daily bullion-report PDFs (gold and silver), IOCL's domestic LPG price list and PPAC's Delhi petrol prices. Each call is cached and logged in the flight recorder.

## How much the replay can prove
- **Only 9 test months** (January to September 2026). The 2024-base series has indices only from January 2025, and 2025 is kept for calibration, so there is no longer history to test on. Nine months is too few to be sure that one method is better than another, and small differences in mean miss may be luck.
- **The 80% range comes from those same 9 replay misses.** With so few months, the range is itself uncertain.
- **Replays search today's web with date filters.** Tavily's published date is a best estimate. The code also checks dates written inside pages, and it drops pages that state the official figure for the month. Still, a replay can never perfectly recreate what was on the web at the time.
- **v1's replay windows ran to each month's last day; a live seal uses evidence up to the 29th, so the replay was slightly easier than live conditions.** Both start 10 days before the month, so that announcements made just before a change takes effect are found (`docs/frozen_rules.md`).
- **v1 used start/end_date plus our own page-date check; filter_by_published_date came later (date test, radar, timelock).** v1's frozen evidence search (`shadow_cpi/evidence.py`, `fetch_pages`) does not send the filter. v1 is frozen, so this is disclosed, not changed.
- **Search filters by date; Extract reads the page as it is today.** A page dated before the cutoff can be updated after it, and Extract returns the updated page. Our page-date check, the October drift monitor and Wayback Machine checks each cover part of this gap, not all of it; numbers in the README section of the same name.
- **2025 is calibration only.** The pass-through factors were fitted on 2025, and nothing was tuned on the 2026 test months. That keeps the test fair, but the factors may not hold in a new series.

## Strong baselines
- **The economists' poll is a strong baseline.** On the 6 months with a dated Reuters poll article, its mean absolute miss was 0.148 percentage points (`results/baselines.csv`). On those same 6 months our nowcast (c) missed by 0.150 after the audit's bug fixes (0.138 before them), so (c) no longer beats the poll on those months; it is level with it at best. Over all 9 months, (c) missed by 0.194 (0.185 before the fixes; `results/scoreboard.md`).
- The simple trend baseline (B2) is also strong, with a mean absolute miss of 0.212 percentage points over the 9 months. The "last month's rate" baseline (B1) missed by 0.468 percentage points on average (`results/score_lock.json`).

## Items are not always what they sound like
- **"Gold" is a composite.** MoSPI's item is *Gold / diamond / platinum jewellery*, not gold alone. We observe the gold rate, but the official item also moves with diamond and platinum prices and with making charges.
- **"LPG" is a composite.** MoSPI's item is *LPG cylinder and piped natural gas* (LPG and PNG together). An LPG cylinder price change moves only part of it.
- **Edible oils** have no single item. We use the *Vegetable oils* sub-class.
- **Silver** is MoSPI's *Silver jewellery*, which also includes making charges.

## How much of the basket we actually see
- Only some items are measured in a given month. The rest of the basket (most services, rents, clothing and so on) is **assumed to follow its recent trend**. The app shows this split every month as the coverage meter. In the replay, 14–21% of the basket was measured each month and the rest followed its trend.
- **The 80% range is too narrow.** In the replay, the official figure fell inside the leave-one-out 80% range in only 5 of 9 months. With 9 months of misses the range is itself uncertain.
- **How the October and November range is built (decided after scoring).** Because 5 of 9 is too few, the live-month range is wider and is not the pre-registered one: it is the prediction plus or minus the 80th percentile of the 9 scored misses of (c), ignoring their sign (± 0.284 pp), and never narrower than the pre-registered range. It is symmetric, so it no longer leans upward the way (c)'s misses did ((c) came in below the official figure in 7 of the 9 months; this is a different count from the 7 of 9 months in which (c) called the direction right, `results/score_lock.json` `direction_hits`). The change was made after seeing the scores, so the 80% label is a judgement, not a tested property; the scored months keep their original ranges and the 5-of-9 figure. The chance that the headline is 6.0% or more (the RBI's Q3 projection) is read from the same range, assuming the miss is normally distributed. Nine misses cannot check that assumption. Details: `docs/frozen_rules.md`, `docs/after_scoring_changes.md`.
- **Government food prices alone did not beat trend.** Food-prices-only (b) missed by 0.225 pp against 0.212 for trend-only; the gain came with the observed gold, silver, LPG and petrol series and the events (c: 0.194 after the audit's bug fixes; 0.185 before).
- A tracked item moves only its own weight (the carve-out). If a big price change happens in something we don't track, we will miss it.

## Models
- Nemotron only extracts facts and cites a numbered line, and code checks that the number is really in that line. A model can still miss a quote or misread a page. Missed quotes lower coverage; misread ones are caught by the check. Every quote shown in the app passed the word-for-word check.

- **v1's keyword matching is not script-aware** (substring and Python `\b`, which treat Indic vowel signs as word breaks); the October radar uses script-aware whole-word matching from logged rule changes R2-R3, on text already normalised by `shadow_cpi.verify.norm` (NFKC, zero-width characters removed; checked 2026-10-27).

## Known gaps in the event layer (2025 recall audit)
- **National brand hikes may be under-weighted.** In the 2025 audit, Amul's ₹2 nationwide milk hike was caught only through a line about the Gujarat cooperative (GCMMF), so it was weighted as a Gujarat-only change (about 7% of milk spending) instead of an all-India one. A regional event counts as national only when the cited line itself says it is nationwide.
- **GST rate cuts are a structural miss.** The 22 Sep 2025 GST cuts changed many items by different amounts, with no single price change to apply, so the event layer does not apply them.

## Independent audit
- **12 events independently audited (AI-assisted search).** Source pages then opened in a browser on
  2026-10-25 by Claude Code: 10 quotes verbatim (9 in the article text, 1 in the page title only), 1 paywalled, 1 not checked (the browser refuses Times of India) (`audit/quote_check.md`). **This differs from
  the 9/1/2 tally reported earlier by Eshan; ours is used everywhere**, with the page date seen for each row. One
  quote is verbatim only in the page's title, not its article text. Eshan audited the 12 verified test-month events
  by web search (`audit/event_audit.md`, PR #4): 5 correct, 3 partly, 3 wrong, 1 unclear. Three different
  confirmation counts, not to be mixed up: **confirmed by another outlet** (the audit's web search): 9 of the 12
  events; **confirmed by Tavily's evidence chase, before the fixes**: 5 of the 12; **confirmed by the evidence chase,
  after the fixes**: 4 of the 9 events left. The 12 became 9 because the fixes below dropped two events and merged two
  into one.
- The three "wrong" rows and the double-counted pair led to four general bug fixes
  (`docs/after_scoring_changes.md` §4): two events dropped, two merged into one, one rail event re-weighted to its
  state. After them, 9 events remain and (c)'s mean miss is 0.194 pp (0.185 before).
- **Left as they are, because they are not bugs in the rules:**
  - **2026-07-E1 (Arokya milk, Tamil Nadu):** sources disagree on the amount (Rs 3 or Rs 4 per litre) and the date
    (9 Jul in other outlets; the event uses 23 Jul). A single news source can carry details that other reports
    contradict.
  - **2026-06-E1 (Uttar Pradesh (UP) 10% electricity surcharge):** announced by UPPCL (UP Power Corporation), but later reports say the regulator put it on
    hold before collection; no official order was found either way. **It is inside the score**: the June prediction
    applies it. News-based events can be reversed after they are announced, and the event layer does not follow
    them up.
- The audit also noted possible misses (a second fuel rise on 19 May, Sanchi milk from 15 May, Gokul from 21 May).
  They were not added: the replay months are not re-searched.

## Method limits found by an outside methodology review
Disclosed only: v1 is frozen and none of these changes a sealed or scored number.
- **Days, not weeks.** We prorate a price change by days in the month; MoSPI collects prices weekly and fuel prices on the 15th, so a mid-month change can count differently in the official figure.
- **A city or route event gets the full state weight.** A bus fare or milk price change in one city or on one route moves the whole state's weight for that item.
- **Electricity is one percentage.** We apply the announced tariff change to the whole electricity item, not to bills by distribution company and usage slab.
- **Delhi petrol stands in for all of India,** and the pass-through from pump price to the CPI item is assumed to be 1.0, not estimated.
- **Milk variety match is not shown.** The app does not show whether the milk variety in a quote is the one MoSPI prices.
- **The carve-out is not fully clean.** The rest of a group, after a tracked item is taken out, still follows a trend that includes that item's own history.
- **Seasonality comes from one year.** The seasonal adjustment uses a single 2025 cycle.
- **v3's weights are judgement calls,** and v3b's inputs overlap (they are not independent of each other).
- **v3's ranges are retrospective.** The ranges are calibrated on the same 9 months, so the Jan-Sep hit rate is not a test; only October and November test them.
- **The Brier score will cover at most two outcomes** (October and November), far too few to judge calibration. The Brier probabilities are from a normal-error model, an assumption nine misses cannot check.
