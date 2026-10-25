# Leak checks P and E: pre-registration

**Written 2026-10-25T19:01Z (UTC) (2026-10-26 00:31 IST), committed at `dcbb7ac` (00:32 IST) before any code for these checks and before any
call.** Decided by the owner. **Exploratory and descriptive**: neither check changes a scored verdict, v1, the v2
locks, the October seal or any earlier check's numbers. The rules below are not changed after results are seen;
a bug fix is logged here with the numbers before and after.

Code (written after this commit): `v2/leakcheck.py`; tests `tests/test_v2_leakcheck.py`. Two caps in
`config/budget.json`: `leakcheck-full-page` **100** and `leakcheck-exact-match` **100**. A cap stops the check
cleanly and marks it incomplete. Not run in 10:00–10:45 IST (the radar session's slot). Output:
`results/leakcheck_full_page.{json,md}` and `results/leakcheck_exact_match.{json,md}`; each result file refuses a
second run.

## Check P: full-page date check (target 0 credits, cap 100)

**Question.** Of the pages that passed a date window, how many carry an explicit date after their cutoff anywhere in
the page text, and how often is that later content rather than page furniture?

### Population (one unit = one distinct URL + cutoff pair within a source)
- **(a) Date test, arm C**: every result kept by arm C (`start_date`/`end_date` + `filter_by_published_date`) in
  `results/date_field_test.json`; cutoff = the case's cutoff. 59 results, 51 distinct URLs.
- **(b) Finance check, arm D**: every result kept by arm D (dates + `filter_by_published_date`) in
  `results/finance_lookahead.json`; cutoff = the event's cutoff. 67 results, 65 distinct URLs.
- **(c) v2 replay, verified evidence**: every page in `v2/evidence/events_2026-0[1-9].json` with at least one
  `verified` claim; cutoff = that month's v2 cutoff (`v2.rules.cutoff`). 20 pages. **Note:** the replay sent
  `start_date`/`end_date` (`v2.rules.window`) but **not** `filter_by_published_date`; these pages passed its date
  window plus the code's own date checks (`best_date` in the window, Amendment D page-date rule). They are taken as
  they are and reported under that description, not as "filter_by_published_date" pages.

### Page text (fixed order; one attempt each)
1. Saved text: (a) the `raw_content` of the date test's own cached Tavily Extract responses (`cache/tavily`, the
   `/extract` calls of `results/date_field_test.json`); (b) none was saved (the finance check used snippets only);
   (c) `v2/evidence/pages/<sha256>.txt` (`page_file` on the card).
2. Only if a unit has no saved text: one Tavily **Extract**, `extract_depth` basic, 5 URLs per call, charged to
   `leakcheck-full-page`. Expected: 5 URLs from (a) (their date-test Extract failed) + 65 from (b) = 70 URLs,
   **at most 14 credits**.
3. Still no text → "no text": counted and listed, left out of the rates' denominators.

### Detector (code, fixed now)
Text is split into lines on newlines. A line is **ignored** if it matches any of these (case-insensitive):
- copyright: `©`, `copyright`, `all rights reserved`, `\(c\)\s*(19|20)\d\d`
- cookie banners: `cookie`
- generated stamps: `page generated`, `generated on`, `generated at`, `last generated`

In every other line, these explicit dates are found (years 2000–2099; Devanagari digits ०–९ read as 0–9; matched
spans are consumed in this order so one date is read once):
1. `YYYY-MM-DD`
2. `DD/MM/YYYY` (day first; one- or two-digit day and month)
3. `DD Month YYYY` (optional ordinal st/nd/rd/th, optional `.` and `,`)
4. `Month DD, YYYY` (comma optional)
5. `Month YYYY` (no day: counts as the month's **first** day, so it is after the cutoff only if the whole month is)

Month = English full names or three-letter abbreviations (Sept also), any case; and Hindi names: जनवरी, फरवरी,
फ़रवरी, मार्च, अप्रैल, अप्रेल, मई, जून, जुलाई, अगस्त, सितंबर, सितम्बर, अक्टूबर, अक्तूबर, नवंबर, नवम्बर, दिसंबर, दिसम्बर.
An impossible date (e.g. 31/02/2026) is skipped. A unit is **flagged** if any date found is strictly after its
cutoff (the cutoff day itself is not flagged).

### Outcome per flagged unit (judged by Claude Code, labelled as such in the output)
Claude Code reads each flagged line with 5 lines of context either side and labels the line:
- **later content**: the page body describes something that happened or was published after the cutoff;
- **sidebar or related links**: the date sits in navigation, a related-stories list, a "trending" box, a comment
  or similar furniture, not the article;
- **benign**: a future date that a pre-cutoff text could state (a scheduled date, a deadline, "valid till", a fiscal
  year end, a target year);
- **unclear**: cannot tell from the text.

A unit takes the first of these that any of its flagged lines has: later content > unclear > sidebar or related
links > benign. Each label carries a one-line reason. The labels are written in a separate file
(`results/leakcheck_full_page_labels.json`) before the report is built, and are not revised after the rates are seen.

### Metrics (per source a, b, c; n = units with text)
1. Flagged rate: flagged / n, **Wilson 95%**.
2. "Later content" rate: later-content units / n, **Wilson 95%**.
3. The four outcome counts; units with no text; credits used.

## Check E: exact_match back-dating (cap 100)

**Question.** If a verified quote is searched verbatim with `exact_match`, does a date-limited search still find it
(the quote existed online by the cutoff), or only an undated one?

### Sample (fixed now)
- Pool: `results/custody.json` rows (as committed at `f07a99f`), **excluding** the one `radar` row (the radar is not
  frozen and belongs to the radar session). Rows with the same quote text and the same cutoff are one quote (the
  first row in file order is kept; same text = same searches). Cutoff = `v2.rules.cutoff(month)`. 53 distinct quotes.
- IDs: the pool sorted by (month, source, page_sha256, quote), numbered Q001–Q053.
- **Seed 20261026**: `random.Random(20261026).sample(pool, 40)`, listed in ID order below.

### Span (fixed rule)
Clean the quote: markdown links `[text](url)` → text; the characters `# * _ \` " “ ”` → spaces; split on
whitespace. Price token = the claim's `price` written plainly (an integer without `.0`, else the shortest decimal,
e.g. 7.25); the first word that contains it as a whole number (commas inside the word ignored) is the anchor; if
none, the first word containing a digit ("number"); if none, the first word. Span = the earliest window of up to 15
words that contains the anchor: words[max(0, anchor − 14) : max(0, anchor − 14) + 15]. All 40 spans have 10–15
words (none under 8).

### Searches (two per quote, in a seeded random order per quote: `random.Random(20261027)`)
Common: query = the span in double quotes, `exact_match` true, `search_depth` basic, `max_results` 5,
`include_published_date` true, no topic (Tavily's default, general), no domains, no language, no country.
- **(1) dated:** `end_date` = cutoff, `filter_by_published_date` true.
- **(2) undated:** no date fields, `filter_by_published_date` false.

### Outcome per quote
- **found before cutoff**: search (1) returns at least one result (reported further as "the source page" or
  "another page only"; source match = same host without `www.` and same path without a trailing slash);
- **found only without dates**: (1) returns nothing and (2) returns at least one result;
- **not found either way**: both return nothing. `exact_match` can return empty results for text that is online;
  this is reported as is, not corrected.
- A call that errors or is stopped by the cap: "not run", listed, left out of the shares.

### Metrics (n = quotes with both searches run)
1. The three shares, each with a **Wilson 95%** interval.
2. Credits per quote (expected 2: two basic searches; **80 credits** for 40).
3. Every call logs Tavily's `request_id` and the response SHA-256 (`recorder.provenance`) in the result file.

### Sample (40 of 53; span = the exact query text, without the surrounding quotes)

| ID | Source | Cutoff | Page SHA-256 (first 12) | Anchor, length | Span |
|---|---|---|---|---|---|
| Q001 | arm B | 2026-01-29 | a69c3e92a219 | price, 15 words | Price Cut) दिए हैं. दिल्ली में इसकी कीमत 99,676.77 रुपये से कम करके अब 92,323.02 |
| Q002 | arm C | 2026-01-29 | 0f28abcf5d98 | price, 15 words | buy tickets on one of the commuter rails will now have to pay an $8, |
| Q004 | v2 scored evidence | 2026-01-29 | 5cbbe7cf846f | price, 15 words | buses, and Access-A-Ride increases by 10 cents, moving a standard ride from $2.90 to $3. |
| Q005 | v2 scored evidence | 2026-01-29 | 5cbbe7cf846f | price, 15 words | Express bus fares also tick up: the full fare goes from $7 to $7.25, and |
| Q006 | v2 scored evidence | 2026-01-29 | 85d49a202f2a | price, 15 words | on the Long Island Rail Road and Metro-North Railroad will increase by up to 4.5%, |
| Q007 | v2 scored evidence | 2026-01-29 | a69c3e92a219 | price, 15 words | किया है, तो वहीं MG Motors पेट्रोल-डीजल और ईवी सभी वैरिएंट की कीमतों में 2% |
| Q008 | arm B | 2026-02-28 | 4f61541f5db6 | price, 15 words | cream milk (buffalo milk) by Rs 2 per litre, from Rs 74 to Rs 76 |
| Q009 | arm B | 2026-02-28 | 5a739d607085 | price, 15 words | Bengaluru Metro To Raise Fares Annually Under New Formula, Limits Yearly Hikes To 5 Per |
| Q010 | arm C | 2026-02-28 | a0bae2afbbd0 | price, 11 words | Pay Rs 1-5 more for Bengaluru metro rides from February 9 |
| Q011 | arm Td | 2026-02-28 | e0a52cd608a9 | number, 15 words | कोलकाता में आज से 19 किलो वाले एलपीजी सिलेंडर की कीमत अब 1844.50 रुपये हो |
| Q012 | v2 scored evidence | 2026-02-28 | bc521c30efce | price, 10 words | Bengaluru Metro fares to increase by 5% from February 9. |
| Q013 | arm B | 2026-03-29 | 7c1d1adf9231 | number, 15 words | Starting March 2, an adult bus fare will cost $2.25, a 50-cent increase. Fares for |
| Q014 | arm C | 2026-03-29 | 64122dc115dc | price, 15 words | हो गई है। इस बढ़ोतरी के बाद इंडस्ट्रियल डीजल की कीमत 87.57 से बढ़कर 109.59 |
| Q015 | v2 scored evidence | 2026-03-29 | 2a3c6b46326c | price, 15 words | Non-subsidised LPG will now cost Rs 913 per 14.2-kg cylinder in Delhi as against Rs |
| Q016 | arm B | 2026-04-29 | 7b23ac472cdf | price, 15 words | बावजूद महाराष्ट्र परिवहन निगम (ST) ने गर्मियों की छुट्टियों को देखते हुए किराए में 10 |
| Q017 | arm Td | 2026-04-29 | 5fed74f0f0c0 | price, 15 words | वैल्यू-फॉर-मनी माना जाता था। इसके साथ ही 859 रुपये वाले प्लान की कीमत बढ़ाकर 899 |
| Q018 | v2 scored evidence | 2026-04-29 | 1980bc50d41e | price, 15 words | लीटर की बढ़ोतरी का निर्णय लिया है। अब शहर में दूध 60 के बजाय 63 |
| Q020 | v2 scored evidence | 2026-04-29 | a4c1ff82be05 | number, 15 words | भी बढ़ोतरी कर दी गई है. मध्य प्रदेश विद्युत नियामक आयोग ने वित्तीय वर्ष 2026-27 |
| Q022 | v2 scored evidence | 2026-04-29 | ee3434c06256 | price, 15 words | Power tariff increase approved: Jharkhand's electricity rates see 6.12% hike; Consumers face higher bills starting |
| Q023 | arm C | 2026-05-29 | 6e703b87b06b | price, 15 words | गाय के दूध की कीमत 60 रुपए से बढ़ाकर 62 रुपए प्रति लीटर कर दी |
| Q024 | arm C | 2026-05-29 | 6e703b87b06b | price, 13 words | फुल क्रीम दूध अब 70 रुपए की जगह 72 रुपए प्रति लीटर मिलेगा। |
| Q025 | arm Td | 2026-05-29 | 2027c2fb99e6 | price, 15 words | राष्ट्रीय राजधानी में पेट्रोल की कीमत अब 97.77 रुपये प्रति लीटर से बढ़कर 98.64 रुपये |
| Q026 | arm Td | 2026-05-29 | 4e1426a40b37 | price, 15 words | The cost to ride PATH trains officially increased from $3 to $3.25 on Monday as |
| Q028 | v2 scored evidence | 2026-05-29 | 1339c7a30def | price, 15 words | Mother Dairy’s Full Cream Milk (FCM) 1-litre pack will now cost Rs 72 compared with |
| Q030 | v2 scored evidence | 2026-05-29 | ba75dcaeed5c | price, 15 words | Petrol price in the national capital has been increased to Rs 97.77 per litre from |
| Q032 | arm H | 2026-06-29 | 61607124244a | price, 15 words | किराया 30 रुपये निर्धारित किया गया था। अब किराये में वृद्धि कर न्यूनतम किराया 20 |
| Q034 | arm Td | 2026-06-29 | 3ab587d1aab6 | price, 15 words | तब एलपीजी सिलेंडर का रेट 42 रुपये से 54 रुपये तक बढ़ा दिया गया था। |
| Q035 | arm Td | 2026-06-29 | c73bb4cf0185 | number, 15 words | दिल्‍ली में अब 5 किलो वाले छोटू गैस सिलेंडर की कीमत 821.50 रुपये हो गई |
| Q036 | arm H | 2026-07-29 | 58461b2c36d1 | price, 15 words | 24 (Friday).Under the revised prices, a one-litre pouch of Nandini ghee will cost Rs 715, |
| Q038 | arm Td | 2026-07-29 | 5530b0e80a5a | price, 15 words | to a maximum of VNĐ19,826 (US$0.76) per litre, while E10RON95-III went up VNĐ547 to VNĐ20,550 |
| Q039 | v2 scored evidence | 2026-07-29 | 6e20ae54a046 | price, 15 words | The State Transport Authority (STA) has approved a 13.56 per cent fare hike for the |
| Q040 | v2 scored evidence | 2026-07-29 | 742b8640b0cb | price, 15 words | The State Transport Authority (STA) has cleared a 13.56% increase in fares for buses operated |
| Q041 | v2 scored evidence | 2026-07-29 | bcc3454dfaf8 | number, 15 words | के बीच बीते जून महीने की शुरुआत में एफटीएल सिलेंडर की कीमत में भी 11 |
| Q042 | v2 scored evidence | 2026-07-29 | ca39be4ee069 | price, 15 words | The Maharashtra State Road Transport Corporation (MSRTC) has increased bus fares by 13.65 per cent |
| Q044 | v2 scored evidence | 2026-08-29 | 5e41e8d8a186 | price, 15 words | Pakistan has hiked petrol prices by Rs 0.45 to Rs 325.43/litre and diesel by Rs |
| Q045 | v2 scored evidence | 2026-08-29 | fb94db703686 | price, 15 words | की कीमत में 2 रुपये प्रति लीटर और दही-पनीर जैसे डेयरी प्रोडक्ट्स के दाम 10 |
| Q046 | v2 scored evidence | 2026-08-29 | fb94db703686 | price, 15 words | को मिलेगा। ऐसे में महाराष्ट्र में गाय के दूध की कीमत 60 से बढ़कर 62 |
| Q047 | arm B | 2026-09-29 | b2bc34e1504f | price, 15 words | के लिए एविएशन टर्बाइन फ्यूल यानी ATF की कीमत 6.28 रुपये प्रति लीटर बढ़कर 121.28 |
| Q048 | arm C | 2026-09-29 | fac6af09abb7 | price, 15 words | कोलकाता में 19 किलो वाले गैस सिलेंडर के दाम 2872.50 रुपये से बढ़कर 2,982 रुपये |
| Q052 | arm H | 2026-09-29 | 9e61a9fffc4c | price, 15 words | by the Joint Electricity Regulatory Commission (JERC) for J&K and Ladakh, introduces an average 6.83 |

**Correction (logged 2026-10-26, before any code or call):** the header's time first read 19:05Z, typed by hand; the
file was written at 19:01Z and committed at 19:02Z (`dcbb7ac`). No rule changed.
