# Language date test: pre-registration (a pilot)

**Written 2026-10-26T18:57Z (UTC), committed before any call.** Task card from the owner (27 Oct, IST). Code:
`v2/lang_date_test.py`; tests: `tests/test_v2_lang_date_test.py`. Run once with `python -m v2.lang_date_test`; the
result file refuses a second run.

**Question.** Do Tavily's date fields keep post-cutoff pages out of Hindi and regional-language results as they did
in English (`v2/DATE_TEST_PREREG.md`, `results/date_field_test.md`)? And what does our page-date check add or cost?

## Cases
- **Frame:** the 29 known 2026 price changes in `v2/recall_reference.json` (transcribed from `audit/missed_events.md`,
  built by hand search, independent of Tavily). A change's **coverage language is set by its state before any
  search**: Maharashtra → Marathi; Tamil Nadu → Tamil; Karnataka → Kannada; West Bengal → Bengali; Telangana and
  Andhra Pradesh → Telugu; the Hindi-speaking states (MP, UP, Bihar, Jharkhand, Chhattisgarh, Delhi and others) and
  national changes → Hindi. Not eligible: Kerala (M7), Odisha (T3), Punjab (E3), J&K (E8): their languages are not on
  the card. No credits are spent to check coverage; "has Hindi or regional coverage" means "is in a state whose press
  writes in that language", an assumption the results can contradict (a case with no on-topic result).
- **Available:** Hindi 15, Marathi 5, Tamil 5; **Kannada, Bengali and Telugu 0** (no reference change in those states).
- **Sample:** 4 per available language, 12 in all, `random.Random(20261027)`, shuffled per language in id order.
  Frozen in `v2/lang_date_test_cases.json`. Two pairs share a query (F1/F4, M8/M9); kept as sampled, as in English.
- Cutoff = the v2 cutoff (`v2.rules.cutoff`). One **frozen query per case in its language**: item words + place +
  month + year. Item words come from `v2/kinds.py` QUERIES (Marathi, Tamil, Hindi milk/electricity) and
  `config/items.yaml` (Hindi); composed from listed words where no ready phrase exists (Hindi LPG/bus/rail, Tamil
  rail "ரயில்" + "கட்டண உயர்வு").

| Case | Lang | Month | Cutoff | Query | Also in English test |
|---|---|---|---|---|---|
| M2 | hi | 2026-04 | 2026-04-29 | दूध के दाम बढ़े मध्य प्रदेश अप्रैल 2026 | yes |
| F1 | hi | 2026-05 | 2026-05-29 | पेट्रोल डीजल के दाम बढ़े भारत मई 2026 | no |
| F4 | hi | 2026-05 | 2026-05-29 | पेट्रोल डीजल के दाम बढ़े भारत मई 2026 | no |
| E7 | hi | 2026-07 | 2026-07-29 | बिजली की दरें बढ़ीं छत्तीसगढ़ जुलाई 2026 | yes |
| M1 | mr | 2026-02 | 2026-02-28 | दूध दरवाढ महाराष्ट्र फेब्रुवारी 2026 | no |
| E2 | mr | 2026-04 | 2026-04-29 | वीज दरवाढ महाराष्ट्र एप्रिल 2026 | yes |
| T2 | mr | 2026-04 | 2026-04-29 | एसटी बस भाडेवाढ महाराष्ट्र एप्रिल 2026 | no |
| M10 | mr | 2026-08 | 2026-08-29 | दूध दरवाढ महाराष्ट्र ऑगस्ट 2026 | no |
| T1 | ta | 2026-02 | 2026-02-28 | ரயில் கட்டண உயர்வு தமிழ்நாடு பிப்ரவரி 2026 | no |
| M8 | ta | 2026-07 | 2026-07-29 | பால் விலை உயர்வு தமிழ்நாடு ஜூலை 2026 | yes |
| M9 | ta | 2026-07 | 2026-07-29 | பால் விலை உயர்வு தமிழ்நாடு ஜூலை 2026 | yes |
| M11 | ta | 2026-09 | 2026-09-29 | பால் விலை உயர்வு தமிழ்நாடு செப்டம்பர் 2026 | yes |

## Arms (the card's three; the English test's labels A, C, D kept so rows line up)
Common: `topic` news, `search_depth` basic, `max_results` 3, `include_published_date` true, the same query,
**`language` = the case's language** (Tavily accepted hi/mr/ta in earlier runs; `filter_by_language` not sent),
`include_domains` = that language's list in `v2/kinds.py` DOMAINS, mode prefer. A and C run close together in a
seeded random order per case (seed + 1).
- **A:** no date parameters, `filter_by_published_date` false.
- **C:** `start_date` = the month's first day, `end_date` = the cutoff, `filter_by_published_date` true.
- **D:** C's results plus our page-date check (Tavily Extract, basic): `v2.date_test.page_date`, **unchanged** from
  the English test, so it reads only English and Hindi date words. It is not extended for Marathi or Tamil: a change
  would make D incomparable with English. Its reader gap is reported, not fixed.
- The English arm B (dates without the filter) is not run: the card names three arms.

## Labels (unchanged; `v2.date_test.label`)
Wayback is the only source for a **confirmed** leak or pre-cutoff page (the card's "Wayback for confirmed leaks only"
read as: no other signal confirms a leak). **L**: no Wayback capture on or before the cutoff, first capture after it,
and Tavily's or the address's date after the cutoff. **P**: a capture on or before the cutoff. **F**: any post-cutoff
date signal without that evidence. **U**: otherwise. Wayback CDX is a logged direct download (as in English). Change
from English, decided now: a failed lookup is retried in the run, 3 tries 5 s apart (the `tools/wayback_retry.py`
rule English needed afterwards); still-failed lookups stay unconfirmed and are counted.

## Metrics (per arm, overall and per language; English first pass beside them)
1. **Leak rate:** cases with ≥1 confirmed leak, x of n, Wilson 95%; leak fraction L/(L+P) with bounds (as English).
2. **Undated share:** results with no Tavily published date / results, per arm and language.
3. **Valid evidence lost:** valid = a P result whose title or snippet names the item (English words plus
   `v2/kinds.py` words in every script); lost = valid results found by any arm and not kept by this arm.
4. **Dated outside the window:** results with a Tavily date outside month start…cutoff (the direct test of C's filter).
5. Paired with English on the 6 shared cases (M2, E7, E2, M8, M9, M11): exact McNemar per arm on confirmed-leak
   cases. C vs D exact McNemar. Credits and median latency per arm. D results with no readable page date.

**Trigger for a FEEDBACK note** ("date fields behave differently by language"), fixed now: in any language, arm C
(a) keeps a Tavily-dated result outside the window, or (b) has an undated share ≥ 20 points above English C's
(English C: 0 of 59), or (c) has a confirmed-leak case (English C: 0 of 20). Otherwise the Field Report says the date
fields behaved as in English, with the 12-case caveat.

## Output and cap
`results/lang_date_test.json` and `.md` (a **pilot**), a Field Report section, and a FEEDBACK_NOTES entry only if
the trigger fires. Credit cap **80** (`lang-date-test` in `config/budget.json`). Expected ≤ 40: 24 searches + at most
16 basic extract calls (≤ 72 URLs, 5 per call). The cap stops it cleanly and marks it incomplete.
