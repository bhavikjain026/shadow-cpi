# Shadow CPI v2: pre-registration

**Written 2026-10-22T03:21:54Z (UTC), before any v2 run.** No v2 search, extraction, prediction or score existed
when this file was committed; the commit that adds it is the timestamp of record.

v1 (everything outside `v2/`) stays frozen: its code, rules, results and scores do not change. v2 lives in `v2/`
and in its own app page. Every v2 Tavily call goes through the existing cached client (`shadow_cpi/tavily.py`) and
the Flight Recorder, under hard credit caps in `config/budget.json`.

## 1. Cutoff rule (the main change from v1)

- For a target month *m*, v2 uses only evidence **published up to 23:59 IST on the 29th of *m*** (or the month's
  last day if it is earlier; February 2026: the 28th). This matches a live seal; v1's replay windows ran to the
  month's last day.
- Searches are date-locked: from 10 days before *m* starts (announcements) to the cutoff.
- Code checks each page's published date (page address first, then Tavily's published date). A page with no
  date, or a date after the cutoff, is not used.
- Each page is saved and its text hashed (SHA-256) at fetch time. The evidence ledger records the published date,
  the effective date, the date we found it, the place, the unit, the price type and the CPI item.

## 2. Who does what

- Tavily Search proposes pages; NVIDIA Nemotron Nano reads the price from the proposed text and cites a line.
- Tavily Extract fetches the page; code verifies that the exact cited line is on the page, that the price is in
  that line, and that the page date is within the window. No model writes a quote or chooses a number.
- Code decides every number, as in v1: index levels combined with the official 2024-series weights, year-on-year
  last, tracked items moving only their own weight.

## 3. Data and scoring

- **January–September 2026 are development data** for v2. v2 is built and debugged on them, so v2's Jan–Sep scores
  are in-sample and are labelled as such. They are not a clean test.
- **Pass rule (decided now):** v2 passes if its mean absolute miss over Jan–Sep 2026 is below both
  "repeat last month" (B1) and "trend only" (B2 = v1 model (a)), against MoSPI's published year-on-year figures.
- **Reported beside v1 whatever the result**, with the same metric (mean absolute miss, direction hit-rate), and
  on the economists' poll months as well.
- **Scored once.** The scoring script writes `v2/score_lock.json` and refuses a second run; any later change is a
  logged bug fix with scores before and after, as in v1.

## 4. What will not happen

- No v1 file, rule or result is changed by v2 work.
- The cutoff, the pass rule and the metric are not changed after any v2 score is seen.
- A v2 result is never presented as v1's, or the other way round.

## Amendment A, before scoring

**Dated 2026-10-22, before any v2 score.** Only the April 2026 milk tracer had been run (no prediction scored).

1. **Spine vs events.** For items covered by the government price spine (DoCA: onion, tomato, potato, tur dal,
   edible oils, atta, milk, eggs), the spine is the source. An announced price change for such an item only fills a
   month or region the spine does not cover; otherwise it is shown as context. Events lead only for items with no
   spine series (electricity, fares, LPG, fuel, tariffs). Where an official observed series exists (IBJA gold and
   silver, IOCL LPG, PPAC petrol), that series is the source and events for the item are context. **No item is moved
   twice.**
2. **Geography.** A city or district event moves the state's item only if a statewide source confirms it (the cited
   line or the page title says it applies across the state, or names the state with no narrower place). Otherwise
   it gets weight = the city's share of the state's urban population, from a documented source listed in
   `v2/city_shares.json` with its citation; if no such entry exists, the event is shown as context only and moves
   nothing. The same rule applies to the needle on the Live build page.

## Amendment B, before scoring

**Dated 2026-10-22, before any v2 score.** The April tracer and one September basket build had been run; nothing
had been scored. In September, Nemotron Nano cited a line but returned no number for most announced price changes
(for example a J&K tariff line stating "6.83%" came back with no % change), so no announced change could be verified.

- **When Nano cites a line but gives no number, the Nemotron Super model (`nvidia/nemotron-3-super-120b-a12b`, the
  v1 extraction model) re-reads that page:** the page text fetched by Tavily Extract. Its claims replace Nano's
  number-less claims for that page; Nano's claims that do carry a number are kept as they are.
- **Code still verifies every claim the same way** (`v2.rules.check`): the page date inside the window, the number
  in the cited line, the line on the fetched page, the item, retail not wholesale, and Amendment A's source and
  geography rules. Super, like Nano, only points to a line; it never writes a quote or chooses a number.
- Each claim records which model read it.

## Amendment C, before scoring: regional-language queries and bus fares

**Written 2026-10-22T07:41:06Z (UTC), before any v2 score and before any run with these queries.**

**Kinds searched** (items with no government spine series, plus milk as context). Each claim's kind is set by code
from words in its cited line, in this order; the CPI item is fixed per kind:

| Kind | CPI item | Role (Amendment A) | Words (any language) |
|---|---|---|---|
| electricity | 04.5.1.0.2.01 Electricity charges | moves | electricity, power tariff, बिजली, वीज, மின், విద్యుత్, ವಿದ್ಯುತ್, বিদ্যুৎ |
| milk | 01.1.4.1.1.01 Milk: liquid | context (spine) | milk, दूध, பால், పాల, ಹಾಲು, ಹಾಲಿನ, দুধ |
| lpg | 04.5.2.2.1.01 LPG cylinder and PNG | context (IOCL list) | lpg, cylinder, cooking gas, सिलेंडर, सिलिंडर, गॅस, சிலிண்டர், సిలిండర్, ಸಿಲಿಂಡರ್, সিলিন্ডার |
| diesel | 07.2.2.1.1.01 Diesel | moves (no official series) | diesel, डीजल, डिझेल, டீசல், డీజిల్, ಡೀಸೆಲ್, ডিজেল |
| petrol | 07.2.2.2.1.01 Petrol | context (PPAC) | petrol, पेट्रोल, பெட்ரோல், పెట్రోల్, ಪೆಟ್ರೋಲ್, পেট্রোল |
| metro | (no confident CPI mapping) | context | metro, मेट्रो, மெட்ரோ, మెట్రో, ಮೆಟ್ರೋ, মেট্রো |
| **bus (new kind; v1 never searched it)** | 07.3.1.2.2.01 Bus/tram fare: occasional | moves | bus, बस, एसटी, பேருந்து, బస్సు, ಬಸ್, বাস |
| rail | 07.3.1.1.2.01 Rail fare | moves | rail, railway, train, रेल, रेल्वे, ரயில், రైలు, ರೈಲು, রেল, ট্রেন |
| mobile | 08.3.4.0.2.01 Telephone charges: mobile | moves | mobile tariff, prepaid, postpaid, recharge, रिचार्ज |

**Query sets, per month** (13 searches; date-locked to the v2 window; `max_results` 10; news domains in the language
"preferred", not required):

- English (4): "electricity tariff hike per unit regulatory commission order"; "milk price hike per litre";
  "bus fare hike metro fare rail fare revision"; "petrol diesel price hike LPG cylinder price mobile tariff hike".
- Hindi (4): "बिजली की दरें बढ़ीं प्रति यूनिट"; "दूध के दाम बढ़े प्रति लीटर"; "बस किराया बढ़ा मेट्रो किराया रेल किराया";
  "पेट्रोल डीजल के दाम बढ़े एलपीजी सिलेंडर".
- One combined query (electricity, milk, bus fares) in each of Marathi "वीज दरवाढ दूध दरवाढ एसटी बस भाडेवाढ",
  Tamil "மின் கட்டண உயர்வு பால் விலை உயர்வு பேருந்து கட்டண உயர்வு", Telugu
  "విద్యుత్ ఛార్జీల పెంపు పాల ధర పెంపు బస్సు ఛార్జీల పెంపు", Kannada
  "ವಿದ್ಯುತ್ ದರ ಏರಿಕೆ ಹಾಲಿನ ದರ ಏರಿಕೆ ಬಸ್ ಪ್ರಯಾಣ ದರ ಏರಿಕೆ" and Bengali
  "বিদ্যুতের দাম বৃদ্ধি দুধের দাম বৃদ্ধি বাস ভাড়া বৃদ্ধি". Regional queries are combined because the 150-credit cap
  does not allow one search per kind per language per month. The regional wording was written by us, not checked by
  native speakers.
- Geography: the state and city names of these languages (e.g. தமிழ்நாடு, తెలంగాణ, ಕರ್ನಾಟಕ, পশ্চিমবঙ্গ, சென்னை,
  ಬೆಂಗಳೂರು, কলকাতা) are added to the place lookup used by Amendment A rule 2.

**Recall (report only).** The 29 known Jan–Sep 2026 changes in `audit/missed_events.md` are transcribed into
`v2/recall_reference.json` (kind, effective month or date, place, v1 status). A change counts as **found directly by
v2** if a claim verified by `v2.rules.check` has the same kind, the same effective month (the same date ±2 days where
the reference gives a day) and, for state changes, the same state. v1's count is the audit's FOUND column (9 of 29).
The result is reported as it comes out; no query, word list or rule is changed because of it.

### Amendment C, recall matcher rules (2026-10-22T08:06:02Z, before any v2 recall number was computed or seen)

The matcher is `v2/recall.py` (`matches`, `score`), tested in `tests/test_v2_recall.py`. A reference change in
`v2/recall_reference.json` counts as **found directly by v2** if at least one claim satisfies all of:

1. **Verified only:** the claim passed `v2.rules.check` (status "verified"). Its Amendment A role does not matter:
   a verified context-only claim (e.g. milk) still counts as found.
2. **Kind:** the claim's kind (from the words in its cited line) equals the reference kind, except that a reference
   of kind **fuel** is matched by a claim of kind **petrol or diesel**.
3. **Date:** the claim's effective date is in the reference month; where the reference gives a day, it is within
   **2 days** of that day (inclusive).
4. **Place:** for a state change, the claim's states (from its region field, cited line, line context and page title,
   with the Amendment C regional names) **overlap** the reference states (one shared state is enough). A national
   change (no states) is matched by a claim from any place.

Each reference change counts once; one claim may match more than one reference change. Recall is computed once.
A matcher bug found afterwards is fixed only as a logged bug fix, with recall reported before and after.
