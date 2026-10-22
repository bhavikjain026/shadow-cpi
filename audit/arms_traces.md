# Search arms: five example traces, and why arm T found nothing

From the arm files in `v2/ablation/` (Amendments E and F, development data). Each trace is one search: who wrote the
query, what was sent to Tavily, what came back, and what the verifier did with each page. Read from the files; no
new calls. Verdicts on unmatched events come from the hand check (`audit/arms_unmatched_check.json`).

## 1. Bad query, arm C, June: "ವಿದ್ಯುತ್ ತರiffe ಜೂನ್ 2026 Karnataka Wisconsin growth"
- **Written by** Nemotron Super (`v2/ablation/arm_C_2026-06.json`). Kannada "electricity", a half-English
  "tariffe", then "Karnataka Wisconsin growth".
- **Sent:** topic news, basic, 6 results, 22 May – 29 Jun, Kannada outlets preferred.
- **Back:** 6 pages, none about electricity: a US college-football piece (si.com), two Bengaluru skill-summit
  releases, an awards conclave, an actor's birthday note. All 6 rejected ("Nano found no price"). 0 verified.
- **Lesson:** a model-written query can drift into nonsense; the date window and the verifier kept it from doing
  harm, but the search was wasted.

## 2. Bad query, arm B, January (and again in September): "बस कि Fahrpreiserhöhung news"
- **Written by** Nemotron Nano (`arm_B_2026-01.json`, `arm_B_2026-09.json`): Hindi "bus of" + German "fare
  increase" + English "news".
- **Back (January):** 5 pages, all foreign: New York's MTA fare rise (NYT, ABC7, CBS, NY Post) and a Guernsey bus
  consultation (BBC). All rejected (not fetched, no claim, or "the line is not about this item"). 0 verified.
- **Lesson:** mixed-language queries pull in foreign news; with `prefer` (not `restrict`) domains, Indian outlets
  are only a preference.

## 3. Good query, arm B, February: "metro fare revision February 2026"
- **Written by** Nano (`arm_B_2026-02.json`). **Sent:** news, basic, 5 results, 1 – 28 Feb.
- **Back:** 5 pages, all on Bengaluru Metro's fare revision. 2 verified (Swarajya headline; Moneycontrol: "Bengaluru
  Metro fares to increase by 5% from February 9"); 3 rejected (price not in the cited line, no price given, and
  The Hindu's "fare hike put on hold" page with no claim to check).
- **Hand check:** a real change **missing from the 29** (Karnataka). The Moneycontrol row also tags Delhi, wrongly.

## 4. Verified but wrong, arm C, March: "पेट्रोल डीजल मूल्य वृद्धि मार्च 2026 भारत"
- **Written by** Super (`arm_C_2026-03.json`). **Sent:** news, basic, 8 results, Hindi, 19 Feb – 29 Mar.
- **Back:** 8 pages on the 20 Mar premium-petrol and industrial-diesel rise. 4 rejected for no publication date, 1
  for no price; 2 kept only as context (commercial / wholesale price). 1 verified (India TV): "industrial diesel up
  Rs 22.02 a litre".
- **Hand check: wrong.** The number is in the line, so it passed the line check, but it is industrial (bulk) diesel,
  not a retail CPI item, and it was tagged LPG. The line check proves a quote is real, not that it is relevant.

## 5. Good query, arm C, May: "दूध की कीमत अप्रैल मई 2026 भारत में बढ़ी"
- **Written by** Super (`arm_C_2026-05.json`). **Sent:** news, basic, 8 results, Hindi, 21 Apr – 29 May.
- **Back:** 7 pages on the Amul / Mother Dairy +Rs 2 rise. 1 page verified 3 claims (Amar Ujala, 14 May: full
  cream Rs 70 → 72; cow milk Rs 60 → 62), **matched to the 29** (M3). The other 6: 4 with no publication date, 2
  with the price not in a cited line.

## Arm T: why Tavily's auto_parameters found 0 of 29
Arm T sent arm B's query texts with `auto_parameters: true` and no dates (as pre-registered in Amendment F). Over
its 72 searches Tavily chose:

| topic | time_range | search_depth | searches |
|---|---|---|---|
| news | w (past week) | advanced | 35 |
| news | w (past week) | basic | 22 |
| news | d (past day) | advanced | 14 |
| general | m (past month) | basic | 1 |

So every search was limited to the days before the run (22 Oct 2026). Of 659 results, 620 were dated October 2026,
1 September 2026 and 38 had no date; every dated one was after the month's cutoff, and the verifier rejected them
all (trace: `arm_T_2026-01.json`, "rail fare hike news India": 10 results dated 16–22 Oct 2026 — Japanese and
Dutch rail fares, a Telangana Dasara bus fare piece — each "published … after the cutoff 2026-01-29"). 0 of 29 is
the pre-registered result. The exploratory arm T+dates sends the same queries with arm A's dates added.

**Correction (logged; no number changed).** The ablation notes said auto_parameters chose "`time_range: \"w\"`,
topic news and advanced depth for every search". The arm files show the mix above (57 of 72 week, 14 past day, 1
past month; 49 advanced, 23 basic). The note is now computed from the arm files.
