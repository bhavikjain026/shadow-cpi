# Shadow CPI: demo video script (DRAFT, 2:45)

Rules for the video:
- Say "experimental nowcast" (never "forecast of the official number" or "prediction of MoSPI").
- Show no company logos: crop browser tabs, and use plain text names.
- Every number below comes from a results file (named in the last column) and matches what the app shows. The only
  number not known yet is the sealed October figure, read off the app on recording day: [I fill in].
- Plain words, calm pace, about 140 words a minute.

| # | Time | On screen | Voice-over | Numbers from |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:12 | App **Home**: the sealed October call, its range, and the countdown to Thu 12 Nov, 4:00 PM IST. Slow zoom on the countdown. | "This is our experimental nowcast of India's October inflation. It's sealed and waiting. On the twelfth of November the government publishes the real number, and then everyone can see how close we got." | `sealed/2026-10.json` |
| 2 | 0:12–0:24 | Same box: SHA-256, sealed time in UTC, "PASS". Then the git tag `seal-2026-10` on GitHub. | "We locked it before the release. This fingerprint changes if even one character of the file changes, and the date is public on GitHub. We can't quietly fix it later." | `sealed/2026-10.sha256` |
| 3 | 0:24–0:38 | Plain title card: "India's CPI comes out ~2 weeks after the month ends." Then: "Until then: hunches and a few polls." | "Inflation drives interest rates and household budgets, but the official number arrives weeks late. Meanwhile the web is full of real prices, if you can find, date and check them." | – |
| 4 | 0:38–0:54 | **Home**: the "How it works" line, then the pipeline diagram from the README. | "Tavily searches the web with dates locked, in English and Hindi, and reads official gold, gas and petrol price lists. Nemotron on Nebius Token Factory only pulls out quoted, dated prices. Plain code does the rest." | – |
| 5 | 0:54–1:10 | **Evidence**, March 2026: the quotes table, the Source column, then open "Exact lines". Click one source to show the same line on the page. | "The model never writes a quote and never picks a number. It points to a line on the page; code copies that exact line and checks the price is really in it." | `manifests/2026-03.json` |
| 6 | 1:10–1:26 | **Evidence**, September: the J&K electricity change with its date. Then **Tavily Flight Recorder**: "One verified event, end to end". | "The event layer finds announced price changes, like this 6.83 percent electricity tariff in Jammu and Kashmir from 1 September. The flight recorder shows the search, the page read, and each model call." | `manifests/2026-09.json`, `results/app/event_chains.json` |
| 7 | 1:26–1:40 | **Replay**: the per-month table, "Measured share" column. | "Each item moves only its own share of the basket. In the replay, 14 to 21 percent of the basket was measured each month; the rest was assumed to follow its recent trend. We always show that split." | `results/replay.csv` |
| 8 | 1:40–2:02 | **Replay**: scoreboard, then the chart: orange actual, blue Shadow CPI with its band. | "Does it work? Replaying January to September 2026, with rules frozen first, Shadow CPI missed by 0.194 points on average. On the six months with an economists' poll: 0.150 against 0.148, about a tie. The official number landed in our range five of nine times, so we widened it for live months." | `results/score_lock.json` |
| 9 | 2:02–2:14 | **Replay**: "One miss explained", January. | "We explain our misses. In January we came in 0.17 points too low. That month our skeptic found three contrary quotes and widened the range, and the official number landed inside it." | `results/replay.csv` (Jan: actual 2.74, c 2.5681, inside range True, note "skeptic: 3 verified contrary quotes"), `results/skeptic_replay.json` (n_contrary 3) |
| 10 | 2:14–2:30 | **Home**: the Independent audit box. | "An independent audit checked our twelve events, and we then opened every source page: nine quotes word for word, one behind a paywall, two unreachable. Five events correct, three partly, three wrong, one unclear. We fixed the bugs with general rules, re-scored once, and show both: 0.185 before, 0.194 after." | `results/app/audit_summary.json`, `audit/quote_check.md`, `results/score_lock.json` |
| 11 | 2:30–2:40 | **Tavily trace (March)**: calls table and the failures list. | "Every Tavily call is on the record: a hundred and seventeen calls for March, what each one asked, what it cost, and what failed." | `results/app/tavily_trace_2026-03.json` |
| 12 | 2:40–2:45 | Back to **Home**: the sealed October call and the countdown. Text: "Shadow CPI: experimental nowcast. Scored on 12 Nov." | "Sealed. Public. Scored on the twelfth of November." | – |

Total: 2:45 (under 2:50).

## Before recording
- [ ] The October call is sealed and shows on Home (the app shows "sealing on 29 Oct" until then).
- [ ] Browser zoom at 110–125% so text reads on a phone.
- [ ] No logos in tabs, bookmarks or the desktop.
- [ ] Do not show `.env` or any key, not even its name in a file listing.
- [ ] Do not press "Run live" on camera before 1 Dec (it is switched off until then and says so).
