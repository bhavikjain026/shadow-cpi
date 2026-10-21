# Honest limits

Shadow CPI is an **experimental nowcast**. It is not an official statistic, and it does not rebuild MoSPI's survey. These are its limits, stated plainly.

## Data we could not get the "proper" way
- **The government price spine is downloaded by hand from behind a CAPTCHA.** The Department of Consumer Affairs report menu (fcainfoweb.nic.in) sits behind a CAPTCHA, which software must not solve, and the site blocks Tavily. `tools/fetch_doca.py` fills in the form in a visible browser and waits; a person types the CAPTCHA. Raw responses are saved in `data/official/doca/raw/` and logged as manual-captcha direct downloads. So the strictest evidence tier does not come in through Tavily, and it is not automatic.
- **The spine is zone-level, not city-level.** DoCA has published only state and national prices since September 2023; the finest monthly report is by zone (5 zones). The all-India rows we add are a simple, unweighted mean of the zones. The report has no day counts (`n_days` is blank). Rice is not taken from the spine: its 2025 fit to MoSPI's rice index was too weak (R² 0.03), so rice is carried on trend.
- **Tavily is blocked on some sites.** Some government and publisher pages refuse Tavily or return no text, for example scanned PDFs. The Evidence page and the Tavily report card list every failed source openly. Where we fell back to a direct download, the report card counts it.
- **MoSPI's official indices come from MoSPI's public API** by a logged direct download (flight recorder service `direct`, raw files in `data/official/mospi_api/`). They are not fetched through Tavily, because Tavily cannot call a paged JSON API.
- **IBJA, IOCL and PPAC come in through Tavily Extract**, not direct downloads: IBJA's daily bullion-report PDFs (gold and silver), IOCL's domestic LPG price list and PPAC's Delhi petrol prices. Each call is cached and logged in the flight recorder.

## How much the replay can prove
- **Only 9 test months** (January to September 2026). The 2024-base series has indices only from January 2025, and 2025 is kept for calibration, so there is no longer history to test on. Nine months is too few to be sure that one method is better than another, and small differences in mean miss may be luck.
- **The 80% range comes from those same 9 replay misses.** With so few months, the range is itself uncertain.
- **Replays search today's web with date filters.** Tavily's published date is a best estimate. The code also checks dates written inside pages, and it drops pages that state the official figure for the month. Still, a replay can never perfectly recreate what was on the web at the time.
- **2025 is calibration only.** The pass-through factors were fitted on 2025, and nothing was tuned on the 2026 test months. That keeps the test fair, but the factors may not hold in a new series.

## Strong baselines
- **The economists' poll is a strong baseline.** On the 6 months with a dated Reuters poll article, its mean absolute miss was 0.148 percentage points (`results/baselines.csv`). On those same 6 months our nowcast (c) missed by 0.138, a small edge on a small sample. Over all 9 months, (c) missed by 0.185 (`results/scoreboard.md`).
- The simple trend baseline (B2) is also strong, with a mean absolute miss of 0.21 percentage points over the 9 months. The "last month's rate" baseline (B1) missed by 0.47 percentage points on average.

## Items are not always what they sound like
- **"Gold" is a composite.** MoSPI's item is *Gold / diamond / platinum jewellery*, not gold alone. We observe the gold rate, but the official item also moves with diamond and platinum prices and with making charges.
- **"LPG" is a composite.** MoSPI's item is *LPG cylinder and piped natural gas* (LPG and PNG together). An LPG cylinder price change moves only part of it.
- **Edible oils** have no single item. We use the *Vegetable oils* sub-class.
- **Silver** is MoSPI's *Silver jewellery*, which also includes making charges.

## How much of the basket we actually see
- Only some items are measured in a given month. The rest of the basket (most services, rents, clothing and so on) is **carried on trend**. The app shows this split every month as the coverage meter. In the replay, 14–21% of the basket was measured each month and the rest was carried on trend.
- **The 80% range is too narrow.** In the replay, the official figure fell inside the leave-one-out 80% range in only 5 of 9 months. With 9 months of misses the range is itself uncertain.
- **How the October and November range is built (Amendment 2, decided after scoring).** Because 5 of 9 is too few, the live-month range is wider and is not the pre-registered one: it is the prediction plus or minus the 80th percentile of the 9 scored misses of (c), ignoring their sign (0.28 pp), and never narrower than the pre-registered range. It is symmetric, so it no longer leans upward the way (c)'s misses did (it under-predicted in 7 of 9 months). The change was made after seeing the scores, so the 80% label is a judgement, not a tested property; the scored months keep their original ranges and the 5-of-9 figure. The chance that the headline is 6.0% or more (the RBI's Q3 projection) is read from the same range, assuming the miss is normally distributed. Nine misses cannot check that assumption. Details: `docs/frozen_rules.md` (Amendment 2), `docs/after_scoring_changes.md`.
- **The government spine alone did not beat trend.** Spine-only (b) missed by 0.225 pp against 0.212 for trend-only; the gain came with the observed gold, silver, LPG and petrol series and the events (c: 0.185).
- A tracked item moves only its own weight (the carve-out). If a big price change happens in something we don't track, we will miss it.

## Models
- Nemotron only extracts facts and cites a numbered line, and code checks that the number is really in that line. A model can still miss a quote or misread a page. Missed quotes lower coverage; misread ones are caught by the check. Every quote shown in the app passed the word-for-word check.

## Known gaps in the event layer (2025 recall audit)
- **National brand hikes may be under-weighted.** In the 2025 audit, Amul's ₹2 nationwide milk hike was caught only through a line about the Gujarat cooperative (GCMMF), so it was weighted as a Gujarat-only change (about 7% of milk spending) instead of an all-India one. A regional event counts as national only when the cited line itself says it is nationwide.
- **GST rate cuts are a structural miss.** The 22 Sep 2025 GST cuts changed many items by different amounts, with no single price change to apply, so the event layer does not apply them.
