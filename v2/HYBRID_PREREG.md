# Arm H, "templates + model-chosen fields": pre-registration

**Written 2026-10-22T17:55:59Z (UTC), committed before any code for it and before any call.** Decided by the owner.
**Exploratory, added after scoring; cannot change the winner (A)**, any verdict of Amendments E/F, v1, the v2 score
locks or the October seal. DEVELOPMENT data (Jan–Sep 2026), as Amendment E.

## Question
Does letting Nemotron choose a search's *filters* (not its words, not its dates) on top of arm A's fixed query text
find more of the 29 known changes than arm A, at what real cost?

## What is sent (per month, Jan–Sep 2026, each month run once, in order)
- **Query text and language label:** arm A's 13 searches exactly (`v2.kinds.QUERIES`, same order, same text).
- **Fixed by code, never by the model:** `start_date`/`end_date` = `v2.rules.window(month)` (same as A);
  `search_depth` basic; `max_results` 10; no `auto_parameters`.
- **Chosen by Nemotron, and only these four fields, per search:** `topic` (one of `news`, `general`,
  `finance`); `include_domains` (0 to 20 host names); `include_domains_mode` (`prefer` or `restrict`);
  `language` (one of `en`, `hi`, `mr`, `ta`, `te`, `kn`, `bn`, or `none` = not sent).

## How the model chooses
One call per month. Nemotron **Nano** gets the month, the 13 query texts with their language labels and index, the
kinds of retail price change we look for (the Amendment C kinds and CPI items; no reference change, no known event,
no dates) and the allowed values above. It returns JSON: one object per index with the four fields. Temperature 0.
If Nano's reply has no usable JSON or covers fewer than 13 indexes, **Super** gets the same prompt once; the better
reply (more valid fields) is used.

## Validation (code, before any Tavily call; each outcome logged next to the search)
A field is **valid** if it is present and allowed: topic in the list; mode in the list; language in the list;
include_domains a list of at most 20 distinct host names matching the same host-name rule as Amendment E
(`v2.ablation.HOST`, after removing scheme, path and "www."). An **invalid or missing field falls back to arm
A's value for that field** (topic news; A's domain list for the query's language; mode prefer; language `hi`
for Hindi queries, otherwise not sent), so every search still runs. A month whose plan has no usable JSON after
Super runs all 13 searches on A's fields and is marked "plan incomplete".

## Reading and scoring (unchanged)
Same reader and verifier as arm A (`v2.pipeline.read_results`, `fetch_and_verify`, Super re-reads under Amendment
B, every check of Amendments A–D), same kind and place rules, same 29 known changes, same matcher (`v2/recall.py`
`matches`, **db2984c**), same reconciliation code as the four-arm table.

## Cache
If the model picks exactly A's fields, the request body equals A's and is served from the cache: 0 real credits, its
original cost still counted in "credits (original cost)".

## Report (one labelled section, "exploratory, added after scoring; cannot change the winner (A)")
1. Recall of the 29, distinct verified events, matched / not matched, false events (upper bound).
2. **Like-for-like with A:** on H's complete months only (and how many of the 29 fall in them), H recall vs A recall.
3. **Real credits** (ledger `real_spent`, budget `v2-ablation-H`) and credits at original cost.
4. **Credits per known change found** (real and original) and credits per verified event.
5. **Fields valid x of y:** y = 4 × searches planned; per field too; and how many valid fields differ from A's value.
6. Plan retries (Super), plan-incomplete months, months cut by the cap.

## Cap
`v2-ablation-H` **230 real credits** in `config/budget.json`. A cap stops the arm cleanly; the months cut short are
marked incomplete and listed. The cap is not raised.
