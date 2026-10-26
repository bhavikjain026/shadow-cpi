# October 2026 radar: pre-registration

**Written 2026-10-22T09:38:55Z (UTC), committed before any radar run.** Decided by the owner. Code: `v2/radar.py`; page:
`app_pages/radar.py`; tests: `tests/test_v2_radar.py`. A **report-only** prospective test: it never changes v1,
the v2 score locks or the October seal.

**What.** Announced retail price changes in India taking effect in **October 2026**, found before MoSPI publishes
October CPI, frozen, then scored against a list built independently afterwards.

1. **Window and freeze.** Evidence window = `v2.rules.window("2026-10")` (21 Sep to 29 Oct). The radar is
   **frozen at 29 Oct 2026, 23:59 IST (18:29 UTC)**: `python -m v2.radar --freeze` writes
   `v2/radar/radar_2026-10.frozen.json` and its SHA-256 and is committed; no run is accepted after that time, and
   nothing is added after the freeze.
2. **Search plan.** The winning strategy of the four-arm table (A fixed, B model-written, C model-written + regional,
   T Tavily auto) under Amendment F's rule (rank 1 of `results/v2_ablation.json` `equivalence.ranking`). It is
   written into this file as a timestamped line **"Search strategy decided: X"** before the first radar run; the code
   refuses to run without it. **Discovery** searches use `include_domains_mode` **prefer**. **Corroboration:** for
   each verified event, where a primary source's domain is known (`v2/radar_primary.json`: regulators, utilities,
   oil companies, dairies, railways, government sites), one search **restricted** (`include_domains_mode`
   restrict) to that domain, same window. **Optional:** at most one Tavily Research call per day with an
   `output_schema` of candidate events, **proposals only** (every hit must pass the verifier); not implemented in
   this commit and off unless added by a later dated line here.
3. **Verification rule.** The v2 verifier, unchanged (Amendments A–D: cited line, number in the line, effective date
   in October, page published in the window, page-date check, retail price type). Two tiers:
   - **verified:** passes the verifier;
   - **corroborated:** verified **and** either **2 independent, non-syndicated publishers** (different registrable
     domains, and their cited lines are not the same text after normalising) or **1 primary source** (a page on a
     `.gov.in` / `.nic.in` domain or a domain in `v2/radar_primary.json`).
   An **event** is a distinct (kind, effective date, set of states), as in Amendment E.
4. **"Tavily-only."** An event of a kind with **no government spine series and no official observed series**
   (Amendment A role "moves": electricity, diesel, bus, rail, mobile) whose verified sources were all found with
   Tavily Search and read with Tavily Extract. These are the changes the October nowcast could know only through
   Tavily.
5. **Effect formula.** Each event's effect on October headline CPI inflation, in percentage points:
   effect = needle(item trend + change × share of October in force × state share) − needle(everything on trend),
   with `v2.needle.yoy` (v1's frozen maths: 2024 weights, index levels, year-on-year last). Share of October in
   force = days from the effective date to 31 Oct ÷ 31; state share = Amendment A rule 2 (`v2.rules.geography`).
   Reported per event and summed for Tavily-only events. Report only: it does not change the sealed call.
6. **Matching rule.** The Amendment C matcher (`v2/recall.py` `matches`, db2984c, unchanged): same kind (fuel =
   petrol or diesel), effective date within ±2 days where the list gives a day, shared state for a state change.
7. **Scoring list and scores.** Built **after the freeze, independently of Tavily** (by hand and with other search
   tools), in `v2/radar/scoring_list_2026-10.json`, each change with the date it was **first reported**. Changes
   first reported after 29 Oct 23:59 IST are **not misses** (left out of recall). For each tier: **precision** =
   radar events that match a listed change ÷ radar events; **recall** = listed changes (first reported by the freeze)
   matched by a radar event ÷ those changes. Scored once (`python -m v2.radar --score`); the score file refuses a
   second run.
8. **Credits.** Cap `radar-2026-10` in `config/budget.json`: **150** proposed; the owner may change it by a dated
   line here before the first run. A cap stops a run cleanly and marks it incomplete.

**Search strategy decided: A (fixed templates), per Amendment F, results 5b1eec0.** Written 2026-10-22T12:11:28Z (UTC), 2026-10-22, before any radar run.

**Domain list fixed, 2026-10-25T13:04:16Z (UTC), before any radar run.** Every primary-source domain was opened directly on
2026-10-25 (no Tavily credits; `v2/RADAR_DOMAIN_CHECK.md`). Replaced in `v2/radar_primary.json`: electricity /
Tamil Nadu tnerc.gov.in → tnerc.tn.gov.in; electricity / Jammu and Kashmir jkserc.nic.in → jpdcl.jk.gov.in; bus /
Karnataka ksrtc.in → ksrtc.karnataka.gov.in. Nothing else in this file changes; strategy A and the 150 cap stand.

**Amendment R1 (logged), 2026-10-25T13:42:19Z (UTC), after run 1 and before run 2.** Decided by the owner, with one technical
change logged alongside it. Rules 3–8 and the 150 cap are unchanged; run 1 stands as run.
1. **Corroboration of a single-source event** (tier "verified") no longer restricts the search to a primary domain.
   It is one news search with arm A's settings: topic news, basic depth, `max_results` 10, the radar window
   (`v2.rules.window("2026-10")`), arm A's English news domains in `include_domains_mode` **prefer**; query =
   "<kind> price <states or India> October 2026". Any new verified page that matches the event (the Amendment C
   matcher) is added to its sources, so a second independent outlet can make it corroborated (rule 3). The primary
   domain list (`v2/radar_primary.json`) is unchanged and still makes a page primary.
2. **Fresh searches each day (technical, logged).** The radar's searches are fixed, so a run on a later day would
   otherwise send the same requests and be served the first day's cached responses. From run 2, the radar's Tavily
   calls bypass the cache (responses are still saved and logged), and the credit cap charges every such call: a
   client that does not read the cache is never treated as "cached" by the budget check. Nemotron reads still use
   the cache (same page text, same reading). Pages already read on an earlier day are not read again.

**Amendment R2 (logged bug fix), 2026-10-26T18:16:01Z (UTC), after run 2 and before run 3.** Decided by the owner.
Rules 1–4, 6–8, strategy A and the 150 cap are unchanged. The verifier's rules are unchanged; only how a keyword is
found in text is fixed. Applies to the radar only (`whole=True` / `whole_words=True`); v1 and the locked v2 scores
keep the old matcher.
1. **Whole-word keyword matching (bug).** Kind words and the verifier's "the line names the item" test matched
   substrings, so "रेल" (rail) was found inside "घरेलू" (domestic). A keyword now matches only as a whole word in
   every script (`v2.kinds.has_word`: a word is a run of letters, combining marks and digits). Added, as whole words,
   only plural and case forms of words already listed (`v2.kinds.FORMS`), no new items or synonyms: bus → buses,
   बसों, बसें, बसच्या; rail → trains, railways; lpg → cylinders; electricity → மின்சார, மின்சாரம். None of the
   saved claims they touch is verified or context (4 claims, all rejected for other reasons), so they change no event.
2. **State from the page (bug).** A claim's states come from the page: place names and state regulators (e.g. JSERC →
   Jharkhand, `v2.kinds.REGULATORS`) in the cited line, its context and the title, all as whole words; then the
   source URL's `/<state>/` path segment; the model's region field only when the page names no state.
3. **Licence areas (new radar-only rule, for runs 3–5).** An electricity tariff for one named distribution licensee
   (`v2.radar.LICENSEES`, e.g. BSL in Bokaro, CESC, Tata Power Mumbai), narrower than the state and with no
   documented share, is context with no effect, the same as an undocumented city event. It changes no saved event.
4. **Effect baseline (bug in rule 5).** Rule 5 subtracted needle(everything on trend); carving the item out swaps its
   group's trend for the item's own trend, so a zero change already moved the needle (rail −0.0010 pp, electricity
   −0.0049 pp). Now: effect = needle(item trend + change × share of October × state share) − needle(item trend + 0);
   a zero change gives exactly 0 pp.
5. **Re-classification of runs 1 and 2** (`python -m v2.radar --reclassify`, saved claims and cached page text,
   0 credits; recorded under `reclassified` in `v2/radar/radar_2026-10.json`). One claim changed status; before → after
   for every saved event:
   - **Indore milk** (milk, 2026-10-01, Madhya Pradesh, verified): unchanged, verified, Madhya Pradesh. Effect: none →
     none (milk is a context kind and moves through its spine series, so rule 5 gives it no effect either way).
   - **"Bihar rail +12.3% from 1 Oct"** (rail, 2026-10-01, Bihar, verified, Tavily-only, effect
     +0.0013340698580721622 pp under the old rule 5; +0.0023777317438522516 pp under the R2 baseline) → **rejected**:
     the cited line names no item as a whole word. Its state is now Jharkhand (URL `/state/jharkhand/`), not the
     model's "Bihar". Real tariff change (JSERC, Bokaro/BSL licence area, domestic HV), found by search, rejected
     under rule 3 after the substring fix; context only, not counted.
   - Radar totals: events 2 → 1; corroborated 0 → 0; Tavily-only events 1 → 0; Tavily-only effect sum
     +0.0013340698580721622 pp → 0 pp.

**Amendment R3 (logged bug fix), 2026-10-26T18:31:13Z (UTC), after R2 and before run 3.** Decided by the owner.
Extends R2's whole-word matching (same radar-only flag) to every keyword list the radar reaches: scope (nationwide,
statewide, national bodies, local markers, narrower-than-state), places, retail/domestic and penalty words, fuel grade
and units. The radar now uses `v2/whole.py`, which imports the v1 and v2 lists unchanged and changes only how they are
matched; `shadow_cpi/event_rules.py` (v1, frozen for the seal) and the locked v2 paths are unchanged.
1. **Rule.** A keyword may not start or end inside a word (letters, combining marks, digits; every script). Patterns
   that carry their own `\b` keep it, made script-aware. **Start-of-word only** (may take an ending, may not start
   mid-word): the regional place names (as in R2); Indian-script state and city names, which take case endings
   (महाराष्ट्रात, दिल्लीत), except असम, धार and यूपी, whose longer forms in the cached pages are other words (असमर्थ,
   धार्मिक, यूपीआई); and the listed stems whose endings are their own plural or case forms in the cached pages
   (`v2.whole.STEMS`: उपभोक्ता → उपभोक्ताओं, ग्राहक → ग्राहकों, तेल कंपनि → तेल कंपनियों, शहर → शहरों, देशभर → देशभरात,
   household → households, procurement price → procurement prices, and the others listed there). Left whole-word
   where the longer words are other words: commercial, industrial, domestic, liter (literature), सामान्य, साधारण.
2. **Hits fixed** (mid-word matches in the 1,574 cached pages that no longer count; counts from those pages):
   शहर inside दशहरा/दशहरे (Dussehra, 118) and सरदारशहर (2), which made a statewide change "narrower than the state";
   देशभर inside प्रदेशभर (9) and देश भर inside प्रदेश भर (1), which made a statewide change nationwide; residential
   inside presidential (85), which hid a commercial line from the domestic test; ftl inside swiftly/softly (7);
   industrial inside deindustrialisation (1); रूट inside फ्रूट (1); मंडी inside गुलमंडी (1); सामान्य inside सर्वसामान्य
   (9+), साधारण inside सर्वसाधारण/असाधारण (6), नियमित inside अनियमित/अनियमितता/विनियमित (5) (fuel grade); धार (Dhar,
   Madhya Pradesh) inside आधार/आधारित/मुसळधार (314); मुंबई inside बृहन्मुंबई/महामुंबई (4); units, not used by the radar:
   ltr inside ultra/poultry, litre inside kilolitre, लीटर inside किलोलीटर/मिलीलीटर. Hindi रांची inside the Marathi हजारांची
   is in v1's `evidence.CITY_HI`, not in the radar's place lists; the matcher test covers it.
3. **Re-classification of runs 1 and 2** (`python -m v2.radar --reclassify R3`, every saved claim re-judged from the
   cached page text with `v2.pipeline.judge`, 0 credits; recorded under `reclassified` in the radar file). Before → after
   per claim: **no claim changed** status, reason, price type, kind or states (96 claims; re-judging with the old
   matcher reproduces every saved verdict, so the harness is exact). In the saved claims' lines and contexts R3
   removes no hit. One card-level fix: the Bokaro card (prabhatkhabar.com) still showed "verified" after R2 although
   its only verified claim was rejected; it is now rejected. Events: Indore milk (milk, 2026-10-01, Madhya Pradesh,
   verified, no effect) → unchanged. Radar totals unchanged: 1 event, 0 corroborated, 0 Tavily-only, 0 pp.
4. **Daily runs** (`tools/radar_daily.sh`) refuse to run unless both R2 and R3 are logged on main.
