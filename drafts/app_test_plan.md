# Judge-style test plan for the deployed app (Sat 24 Oct 2026)

**Goal:** use the live app the way a judge would, on a phone and on a laptop, and write down everything that is
slow, broken, confusing or does not match the results files.

**How:** two people. One clicks, the other checks numbers against the files in the repo (main branch, latest commit).
Write each problem in the log at the bottom as PASS / FAIL with a screenshot. Do not change code during the test.
Fix afterwards, one item at a time.

**Before starting, note:**
- App URL: [fill in]
- Commit deployed: [fill in]
- Time started (IST): [fill in]
- Devices: phone model + browser [fill in], laptop + browser [fill in]

## 1. First load and cold start
- [ ] Open the URL in a **private/incognito window** (no cache) on the laptop. Time it until the Home page shows a number. Target: under 30 s. Write the time down.
- [ ] Repeat on the phone on **mobile data**, not Wi-Fi.
- [ ] If the host puts the app to sleep (e.g. a "wake this app up" screen), note what a judge sees and how long waking takes. The app must stay live and free until judging ends (16 Dec 01:30 IST).
- [ ] No **SAMPLE DATA** warning and no "(SAMPLE)" tag anywhere. That would mean `SHADOW_CPI_DATA_DIR` is not set on the host.
- [ ] The browser tab title says "Shadow CPI". The sidebar text says "experimental nowcast … Not an official statistic."
- [ ] Reload 3 times. Nothing changes between reloads, and no error box appears.

## 2. Saved run vs "Run live"
- [ ] **"Run now"** button: it must say clearly that this is the **cached** scan and when it ran (UTC), the window, and the receipt (Tavily calls, credits, seconds, Nemotron calls).
- [ ] The wording does not suggest a live run happened when it did not. Today the page says "Live runs come later" and "live scans are not switched on yet". Check that this matches what Bhavik has deployed.
- [ ] **"Try to prove this wrong"** button: shows the cached skeptic result for the month, the counter-searches and whether the range was widened, or a clear "no cached result yet".
- [ ] Press each button twice quickly. There are no duplicate tables and no error.
- [ ] If live scans are switched on by the test date: one live scan works, shows a receipt, and the "scans left today" count goes down by one.

## 3. Every page, phone and laptop

Do each page on both devices. On the phone, also try landscape.

| Page | What to check | Phone | Laptop |
|---|---|---|---|
| Home | countdown to the next release (12 Nov, 4:00 pm IST); headline %; 80% range; "inside the range in N of 9"; coverage bar; top 3 contributors; Tavily line; seal fingerprint + PASS | [ ] | [ ] |
| Evidence | month picker; price quotes; events table (exact line + link); spine table; kept/dropped counts; failed sources; code commit + model IDs | [ ] | [ ] |
| Replay | scoreboard table; predicted vs actual chart with shaded range; "one miss explained"; Tavily month-by-month table | [ ] | [ ] |
| Tavily Flight Recorder | credit total; log table loads in under 10 s; "one item, end to end"; evidence-chase tree | [ ] | [ ] |
| Archive | October seal: fingerprint, git tag, sealed-at time, "Download sealed JSON" works; the `sha256sum` instruction | [ ] | [ ] |
| Reporter brief | text loads; mentions "coverage" and "range"; download works | [ ] | [ ] |

On the phone, specifically:
- [ ] Wide tables scroll sideways inside the table, not the whole page.
- [ ] The sidebar menu opens and closes. Every page can be reached from it.
- [ ] Charts are readable without zooming. Axis labels are not cut off.
- [ ] Buttons are big enough to tap.

## 4. Broken links
- [ ] Click **every** link in the Evidence events table for at least 3 months (include April and September). Note any 404, paywall, or page that does not contain the quoted line.
- [ ] Known risks from the event audit (`audit/event_audit.md`): 2026-07-E1's link is a 9 Jul article about Aavin lassi; 2026-09-E1 is a wholesale story. A judge may click these.
- [ ] Links to the GitHub repo, README, demo video and Devpost page (wherever they appear) open the right page.
- [ ] Downloads (sealed JSON, reporter brief) open and are not empty.

## 5. Confusing words

Read every page as someone who has never heard of the project. Mark each term that is not explained on the page
where it first appears:

- [ ] "nowcast" / "experimental nowcast"
- [ ] "YoY" / "year-on-year", and "pp" (percentage points)
- [ ] "carried on trend" / "coverage"
- [ ] "spine" / "government price spine"
- [ ] "carve-out"
- [ ] "(a) / (b) / (c) / (c-strict)", "B1", "B2"
- [ ] "80% range" (and that it was widened for live months: Amendment 2)
- [ ] "sealed" / "fingerprint" / "SHA-256"
- [ ] "credits", "cached"
- [ ] "FPPAS" or other tariff jargon in event lines
- [ ] Any number shown without a unit (%, pp, Rs)

## 6. Every number on screen matches the results files

Check against the files on the deployed commit. Write the screen value and the file value side by side.

| On screen | File to check | Screen | File | OK? |
|---|---|---|---|---|
| Headline nowcast % (Home) | `results/nowcast_latest.json` → `headline_yoy` | | | [ ] |
| 80% range low / high | `results/nowcast_latest.json` → `range_low`, `range_high` | | | [ ] |
| "Inside the range in N of 9" | `results/replay.csv` → count of `c_inside_range` = True (should be 5 of 9 per `results/scoreboard.md`) | | | [ ] |
| Coverage measured / carried | `results/nowcast_latest.json` → `coverage` | | | [ ] |
| Top 3 contributors (pp) | `results/nowcast_latest.json` → `contributors[:3]` | | | [ ] |
| Tavily line (with / without) | `results/nowcast_latest.json` → `tavily_attribution` | | | [ ] |
| Seal fingerprint | `sealed/2026-10.sha256`, and run `sha256sum sealed/2026-10.json` yourself | | | [ ] |
| Scoreboard: mean miss for (a), (b), (c), (c-strict), B1 | `results/scoreboard.md` | | | [ ] |
| Scoreboard: poll on its 6 months | `results/scoreboard.md`, `results/baselines.csv` | | | [ ] |
| Each month's actual, (c), range (spot-check 3 months) | `results/replay.csv` | | | [ ] |
| Flight recorder credit total | `results/credit_ledger.jsonl` / `logs/flight_recorder.jsonl` (uncached Tavily calls only) | | | [ ] |
| Evidence counts for one month (pages seen/kept, quotes, events) | `manifests/<month>.json` → `counts` | | | [ ] |
| Event % in the Evidence table (spot-check 3) | `manifests/<month>.json` → `events[].pct_change` | | | [ ] |
| Countdown dates | 12 Nov 2026 16:00 IST; Nov data 14 Dec (likely), per `audit/dates_check.md` | | | [ ] |

Also check rounding: the same number should show the same decimals everywhere (e.g. 2 decimals for %).

## 7. When the credit cap is reached
- [ ] Find where the cap shows (Home → "Run now": "N live scans left today", daily cap 2, up to ~20 credits each). Caps are in `config/budget.json` (`run-now` 120 total, `run-now-scan` 8).
- [ ] If live scans are on: use up the daily cap (or ask Bhavik to set a test cap of 1 on a test copy, **not** the real app). Then press "Run now" again. Expected: a clear message that today's live scans are used up, the cached result still shows, nothing crashes, and **no Tavily call is made** (check the flight recorder).
- [ ] The next day (or after the reset time), the count resets. Note the reset time and time zone shown.
- [ ] If live scans are off: confirm the page never claims a live scan ran, and the cap text isn't misleading ("2 left today" while scans are off may confuse a judge).
- [ ] Check that the overall Tavily balance can't be drained by repeated clicks from many visitors. Ask Bhavik how the cap is enforced (per app, not per visitor?).

## Log

| # | Page / step | Device | PASS/FAIL | What happened | Screenshot | Who fixes |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
