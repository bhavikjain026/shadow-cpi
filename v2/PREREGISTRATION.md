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

## Amendment D, before scoring (issue 14)

**Written 2026-10-22T08:12:03Z (UTC), before any v2 score.** Decided by the owner. The issue 4 recall run (Amendment C
queries, cap 150) was still running; no v2 prediction had been compared with an official figure.

1. **Range.** v2's 80% range is the prediction ± **0.284** percentage points: v1's live-month half-width from
   Amendment 2 (`docs/after_scoring_changes.md`). No range is fitted on v2's own Jan–Sep misses.
2. **Poll.** The economists' poll is compared on v1's 6 poll months, **unfiltered**. The PRD's rule "the poll
   baseline uses only polls published before the same cutoff" is removed: polls are published about 10 days after
   our 29th cutoff, so the poll uses more information than v2 and is the tougher benchmark. Keeping it unfiltered
   cannot flatter v2.
3. **Targets.**
   - **Pass rule** (unchanged): v2 passes if its mean absolute miss over Jan–Sep 2026 is below both "repeat last
     month" (B1) and "trend only" (B2 = v1 model (a)).
   - **"v2 better than v1"** only if v2's mean absolute miss is lower than v1's (0.194 pp, after Amendment 3)
     **and** v2 finds more than 9 of the 29 known changes directly (Amendment C matcher).
   - **Reported only, no target:** actual inside the 80% range, basket share measured, lift from web evidence (the
     needle with the government spine only vs with all evidence), and quotes rejected for a page date after the
     cutoff.
4. **Basket measured.** v2's definition: a spine or official-series item counts with its full CPI weight; an
   announced change counts with its item's weight times the share it moves (its state's share, or 1 if national).
   v1 is recomputed under the same definition for the comparison: a recalculation of a reported measure, not a
   re-score.
5. **Page date from the page itself.** Besides the date from the page address or Tavily's published date, the
   verifier reads the date **printed on the fetched page**: dates next to words such as published, updated, posted,
   प्रकाशित, अपडेट, or followed by a clock time; the latest such date is the printed date. A quote is rejected if the
   printed date is **after the cutoff**, or if it is **more than 2 days later than Tavily's published date** (flagged
   as "page edited after its date"). A page with no printed date is not rejected for that reason. Both rejections are
   counted for the audit view, and a verifier test covers a page edited after its date.
6. **Price type (display only).** Each ledger record stores `price_type`: household **retail**, **wholesale** or
   **commercial**. Wholesale and commercial prices that pass every other check are kept as visible **context**
   cards; they never enter the number.

**Issue 14 procedure.** For each month Jan–Sep 2026, cutoff the 29th (February: the 28th):
- the government spine items (Amendment A rule 1), and the official series cut at the cutoff (v1's code);
- announced price changes from the Amendment C query set, verified under Amendments A–D (reusing the cache from the
  issue 4 run, completing any month it did not reach), one event per item × place × month;
- the needle (`v2.needle`), range ± 0.284, direction scored with v1's pre-registered rule against B1.
Scored once; `results/v2_score_lock.json` refuses a second run; credit cap 250 (`v2-issue14`).

**Deviations from the PRD (logged).** Amendment B uses Nemotron Super, which the PRD does not list (it lists Nano for
reading and Ultra for refereeing). The verifier fetches the **full page** with Tavily Extract instead of the PRD's
"focused query per item, a few chunks", because checking the exact cited line needs the whole page. Board issues
5 (official-site Map and Crawl), 6 (Research sweep) and 7 (Ultra referee) are cut before scoring.

## Amendment E, search-parameter ablation (DEVELOPMENT data, report only)

**Written 2026-10-22T09:14:19Z (UTC), before any code for it was written and before any run.** Decided by the owner. v1 and the v2
score lock (results/v2_score_lock.json, results/v2_recall_lock.json) are final and are not changed by anything here.

**Question.** Does letting Nemotron write each Tavily search (its query and its filters) find more of the known price
changes than our fixed query templates, at what cost?

**Data label.** Jan–Sep 2026 have already been scored and the 29-change reference set was built from them, so every
result here is **DEVELOPMENT data**, not a test. No rule, query or score in v1 or the v2 locks is changed because of it.

**Three arms**, each run **once** on each month Jan–Sep 2026, same window and cutoff (`v2.rules.window`: 10 days
before the month to the 29th), same reader and verifier (search proposes → Nano reads → Extract verifies, Super
re-reads under Amendment B, every check of Amendments A–D), same kind and place rules (`v2.kinds`):

| Arm | Who writes the searches | Languages | Searches per month |
|---|---|---|---|
| **A** fixed templates | code: the 13 Amendment C queries, exactly as in issue 14 (topic news, max_results 10, window dates, the language's news domains preferred) | en, hi, mr, ta, te, kn, bn | 13 |
| **B** model-written | Nemotron | English and Hindi only | 8 (at least 3 English, 3 Hindi) |
| **C** model-written + regional | Nemotron | en, hi, mr, ta, te, kn, bn | 13 (at least 3 English, 3 Hindi, 1 in each regional language) |

**How the model writes a search (arms B and C).** One call per month and arm. Nemotron **Nano** gets: the month, the
window start and cutoff dates, the kinds of retail price change we look for (the Amendment C kinds and their CPI
items, no reference change and no known event), the allowed languages and counts, and the allowed values below. It
returns JSON, one object per search: `query`, `language`, `topic`, `start_date`, `end_date`,
`include_domains`, `include_domains_mode`, `max_results`. If Nano's reply has no usable JSON or gives fewer
valid searches than the arm needs, **Nemotron Super** gets the same prompt once; the arm then runs the valid searches
it has, and a month with fewer than required is marked "plan incomplete". Temperature 0.

**Code validates every parameter before any Tavily call** (each correction is logged next to the search):
- `query`: non-empty, at most 400 characters; otherwise the search is dropped.
- `language`: one of the arm's languages; otherwise the search is dropped. As in arm A, it is sent to Tavily as
  `language` only for Hindi; for every language it is recorded and decides the query's script.
- `topic`: "news" or "general"; anything else becomes "news".
- `start_date`, `end_date`: ISO dates inside the window (window start to the cutoff), start ≤ end; a date outside
  is clamped to the window edge, a missing or unreadable one becomes the window edge.
- `include_domains`: host names only (lower case, "www." removed); at most **20** (the rest dropped); may be empty.
- `include_domains_mode`: "prefer" or "restrict"; anything else becomes "prefer".
- `max_results`: an integer 1–10; outside is clamped, missing becomes 10.
- search depth is always "basic" (cost is fixed by code, not by the model). The page-date and window checks of the
  verifier use the pre-registered window, never the model's dates.

Every written parameter, the model that wrote it, each correction and what was sent to Tavily are saved
(`v2/ablation/`), logged in the flight recorder, and shown on the Tavily trace page.

**Metrics** (computed by code after all three arms have run, once):
1. **Recall:** known changes found directly, of the 29 in `v2/recall_reference.json`, with the matcher committed in
   db2984c (`v2/recall.py` `matches`, `score`), unchanged.
2. **False events:** an *event* is a distinct (kind, effective date, set of states) among an arm's verified claims
   whose kind moves CPI under Amendment A (electricity, diesel, bus, rail, mobile). A false event is one that matches no
   reference change under the same matcher rules. The reference set is the audit's list, so this is an **upper
   bound** on false events, labelled as such.
3. **Credits per verified event:** the Tavily credits of every search and extract the arm made (Tavily's own
   `usage.credits` in each response, counted whether the response is new or served from the cache, so arm A is
   costed as when first run), divided by the arm's distinct verified events of any kind (same distinctness rule).
4. **Median latency:** the median of Tavily's own `response_time` over the arm's search and extract calls.

**Credit caps** (config/budget.json): arm A runs from the cache only (0 new credits; a cache miss is recorded, not
fetched); arm B `v2-ablation-B` 170; arm C `v2-ablation-C` 230; **400 in total**. A cap stops the arm cleanly; the
months cut short are listed and their figures marked incomplete. Results: `results/v2_ablation.json` and
`results/v2_ablation.md`, one table: arm → recall, false events, credits per verified event, median latency.

### Amendment E addendum: reported-only diagnostics

**Written 2026-10-22T09:23:34Z (UTC), while arms B and C were still running and before any Amendment E metric was computed.**
Decided by the owner. These are **reported only**: no target, and they change none of the four pre-registered
metrics. Computed by `v2.ablation.diagnostics` in the same single `--metrics` run, per arm:
- **Credits per verified event** and **false events (upper bound)**: the pre-registered metrics 2 and 3, shown
  beside the diagnostics so the arms are compared on cost as well as recall.
- **Duplicates:** (a) duplicate results = search results whose page another search in the same arm and month had
  already returned; (b) duplicate verified claims = verified claims minus distinct verified events.
- **Validation failures:** model-written parameters corrected by code, and model-written searches dropped by code.
- **Retries:** plan calls handed to Super after Nano failed; Amendment B Super re-reads of fetched pages.
- **Abstentions:** plan calls that wrote fewer searches than asked (including none); in-window pages where Nano
  found no price in the search text (of the pages read).
- **Structured fields check:** from the exact JSON bodies POSTed to Tavily /search (the recorder's cache, found by
  each call's cache key): how many carry `start_date`/`end_date`, `topic` and `include_domains` +
  `include_domains_mode` as API fields, how many Hindi searches carry `language`, and how many queries contain a
  parameter name as text (expected 0). Three example request bodies are shown verbatim in the report; the API key is
  sent in the Authorization header and is never in a body.

## Amendment F: equivalence margin, arm T (Tavily auto parameters), provenance

**Written 2026-10-22T09:27:44Z (UTC), before any Amendment E metric was computed** (arm B was still running, arm C not started).
Decided by the owner. Nothing here changes v1, the v2 score locks or Amendment E's four metrics.

1. **Equivalence margin.** On recall, arms within **±1 known change** (of the 29) count as **about equal**. The
   top group is every arm whose recall is at least the best arm's recall minus 1. Within the top group, arms are
   compared on **credits per verified event** (lower is better), then **false events** (upper bound; lower is
   better). An arm outside the top group is reported as lower recall.
2. **Arm T, Tavily auto parameters.** For each month Jan–Sep 2026, the **same query texts as arm B** (B's validated
   searches for that month, in order) are sent to Tavily /search with **`auto_parameters: true`** and
   `max_results` 10 (Tavily requires max_results to be set by the caller; 10 as in arm A), and **no other filter**:
   no topic, dates, domains, language or search depth from us or from the model, so Tavily chooses them (it may
   choose advanced depth at 2 credits). The `auto_parameters` object Tavily returns is logged for every search.
   Results then go through the same reader and verifier as the other arms, with the pre-registered window (a page
   outside it is rejected). Same 29 known changes, same matcher (db2984c), same four metrics and the same
   reported-only diagnostics. Run once. Credit cap `v2-ablation-T` **200** (each search budgeted at 2 credits); a
   cap stops the arm cleanly and the months cut short are listed.
3. **One table, computed once.** All four arms (A fixed templates, B model-written, C model-written + regional,
   T Tavily auto) in one table, computed once by `python -m v2.ablation --metrics` after arm T finishes, with the
   equivalence verdict of point 1.
4. **Provenance for every run from now on** (including the seal's evidence manifest and nowcast file): each Tavily
   call stores Tavily's `request_id` and a **SHA-256 of the response** (the response JSON serialised with sorted
   keys, no spaces, UTF-8) in the flight recorder, the credit ledger, the v2 evidence ledger rows (search and
   extract), the ablation arm files, and a `tavily_provenance` list in the manifest and nowcast file. Provenance
   only: no number changes. Runs before this commit (including arm C, started under the earlier code) do not carry
   it.

### Exploratory arm T+dates

**Written 2026-10-22T12:26:37Z (UTC), before it was run.** Exploratory arm T+dates (added after scoring; cannot change the winner
or any verdict): same queries as T, auto_parameters=true, plus the same start_date/end_date windows arm A used. No
other fields from us. Cap 190 credits. Reported in its own labelled section.

**Bug fix (logged) 2026-10-22T17:04:44Z, before T+dates resumes; no result or score number changes.**
`Budgeted.search` added `search_depth: basic` to `auto_parameters` searches, which `Tavily.search` does not send,
so the cap's cache check never matched them: T+dates searches served free from the cache were charged to the ledger
again. Found after the first T+dates run stopped mid-February. Phantom so far: 4 credits (calls af08b01d1d32 and
00eca106d1e5, 2026-10-22T14:31:10Z, both `cached: true` in the flight recorder); those rows stay in the ledger,
offset by one correction row (-4, `phantom_of` both call ids), so the 190 cap counts real credits only. From now
on every ledger row carries `real_spent` (what caps count; `credits` = `real_spent`) and `original_cost`
(Tavily's own count when the call was first made); cache hits in runs that can spend write a row with
`real_spent: 0`, `cached: true`. Credits per verified event still counts every call at its original cost (arm
files, `calls[].credits`), as for the four-arm table. Test: tests/test_budget_reserve.py.

**Arm T credit correction (logged) 2026-10-22, after the T+dates run; no metric, recall or verdict changes.** The
same budget bug (070fa6e) charged 41 of arm T's 72 searches again although they were cache hits (65 credits; arm
T's real spend was 56, not 121). The rows stay in the ledger, offset by one correction row (-65,
`phantom-T-2026-10-22`, `phantom_of` the 41 call ids). `results/v2_ablation.json` arm T `new_credits` 121 → 56;
`credits` stays 121, because credits per verified event counts every call at its original cost.
