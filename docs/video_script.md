# Shadow CPI: demo video script (DRAFT, 2:45)

Rules for the video:
- Say "experimental nowcast" (never "forecast of the official number" or "prediction of MoSPI").
- Show no company logos: crop browser tabs, and use plain text names.
- Every number on screen must come from the real app. Wherever this script says [TBD: from replay], read the number off the app on recording day.
- Plain words, calm pace, about 140 words a minute.

| # | Time | On screen | Voice-over |
| --- | --- | --- | --- |
| 1 | 0:00–0:12 | App **Home**: big October number, range, and the countdown "Next MoSPI release: October 2026 CPI, 12 Nov". Slow zoom on the countdown. | "This is our experimental nowcast of India's October inflation. It's sealed and waiting. On the twelfth of November the government publishes the real number, and then everyone can see how close we got." |
| 2 | 0:12–0:24 | Same screen, scroll to the **Seal** box: SHA-256, git tag `seal-2026-10`, sealed time in UTC, "Fingerprint check: PASS". | "We locked it before the release. This fingerprint changes if even one character of the file changes, and the date is public on GitHub. We can't quietly fix it later." |
| 3 | 0:24–0:40 | Plain title card: "India's CPI comes out ~2 weeks after the month ends." Then: "Until then: hunches and a few polls." | "Inflation decides interest rates, wages and household budgets. But the official number arrives weeks late. Until then people guess. Meanwhile the web is full of real prices, if you can find them, date them and check them." |
| 4 | 0:40–0:58 | `docs/pipeline.md` diagram, highlight the Tavily box. | "Every web page comes in through Tavily. Search with a date window finds price news in English and Hindi. Extract reads the pages. Map and Crawl read official tariff orders. A gold rate page gives daily gold and silver prices." |
| 5 | 0:58–1:14 | **Evidence** page: the quotes table, with the "Exact line" column highlighted. Click one link to show the same line on the source page. | "The AI model, Nemotron, only extracts. It points to a line on the page, then plain code copies that exact line and checks the price is really in it. The model never writes a quote, and it never picks a number." |
| 6 | 1:14–1:30 | **Evidence** page: the events table (e.g. a milk price change with its effective date). Then **Flight Recorder**: the evidence chase tree. | "The event layer looks for announced price changes, like a milk price hike or an LPG revision, with the date they take effect. When one checks out, Tavily chases it: same change elsewhere, and the official circular." |
| 7 | 1:30–1:44 | **Home**: coverage meter, then the top 3 contributors. | "Then code does the maths with the official weights. Each item moves only its own share of the basket. Here, [TBD: from replay] percent of the basket is measured this month, and the rest is carried on trend. We always show that split." |
| 8 | 1:44–2:06 | **Replay** page: scoreboard, then the predicted-vs-actual chart with the range band. | "Does it work? We replayed January to September 2026 without tuning on those months. Mean miss: [TBD: from replay] points. The economists' poll: 0.15. The official number landed inside our range in [TBD: from replay] of 9 months." |
| 9 | 2:06–2:18 | **Replay**: "One miss explained". | "And we explain our misses. In [TBD: from replay] we were off by [TBD: from replay] points, because [TBD: from replay]." |
| 10 | 2:18–2:30 | **Home**: press "Try to prove this wrong", and show the cached result and receipt. | "Don't trust us? Press 'Try to prove this wrong'. It searches for evidence against our biggest drivers, and it widens the range if it finds any. Each run shows exactly what it cost." |
| 11 | 2:30–2:40 | **Flight Recorder**: log table, credits total. | "Every outside call is on the record: what was asked, what came back, credits and time." |
| 12 | 2:40–2:45 | Back to **Home**: the sealed October number and the countdown. Text: "Shadow CPI: experimental nowcast. Scored on 12 Nov." | "Sealed. Public. Scored on the twelfth of November." |

Total: 2:45 (under 3:00).

## Before recording
- [ ] Real data in the app (not SAMPLE). Check that no "SAMPLE" label is visible.
- [ ] Every [TBD: from replay] replaced with numbers read from the app.
- [ ] Browser zoom at 110–125% so text reads on a phone.
- [ ] No logos in tabs, bookmarks or the desktop.
- [ ] Do not show `.env` or any key, not even its name in a file listing.
