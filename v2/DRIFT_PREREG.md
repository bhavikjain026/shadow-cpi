# October 2026 page drift, radar skeptic and leaks by source type: pre-registration

**Written 2026-10-26T18:53:31Z (UTC) = 27 Oct 2026, 00:23 IST, on branch `drift-monitor` from `7036cad`, committed
before any drift run, any skeptic search, and before counting any leak by source type.** Decided by the owner (task
card of 27 Oct 2026). Code: `v2/drift.py`, `v2/radar_skeptic.py`, `v2/leak_types.py`; tests: `tests/test_v2_drift.py`,
`tests/test_v2_radar_skeptic.py`, `tests/test_v2_leak_types.py`.

All three parts are **descriptive only**. None changes a forecast, the v1 seal, the v2 score locks, a radar tier, a
radar effect or the radar freeze.

## A. Drift monitor

1. **Which URLs** ("the October evidence bundle"). Every distinct URL among the radar's cards
   (`v2/radar/radar_2026-10.json`: `cards` plus every corroboration search's `cards`) that has **both** a saved page
   copy (`page_file` under `v2/evidence/pages/`) **and** at least one cited line (`claims[].line`). The set is
   re-read from the radar file at each run, so pages added by later radar runs join it. 50 URLs qualify at this
   commit. A URL is not checked on the UTC day its saved copy was fetched (`found`): it was read minutes earlier.
2. **When.** Once a day per IST date, run from `tools/radar_daily.sh` after the radar step, until the radar freeze,
   **29 Oct 2026, 23:59 IST (18:29 UTC)**. No run is accepted after the freeze, and a second run on the same IST
   date does nothing.
3. **Fetch.** Tavily Extract, `extract_depth` basic (the radar's own setting), 5 URLs per call (1 credit per call,
   as `shadow_cpi.budget.call_cost`), through `Budgeted` with budget **`drift-2026-10`**. Cap **60** credits, read
   from `config/budget.json`. A refused call stops the run cleanly and marks it incomplete; unchecked URLs are listed.
   A URL Tavily cannot fetch is logged as "fetch failed", never as changed.
4. **Normalise** (the same steps for the saved copy and the new text): split into lines; drop every line that
   matches the page-furniture rule already used by the leak check (`v2.leakcheck.IGNORE`: ©, copyright, all rights
   reserved, (c) year, cookie, page generated / generated on / generated at / last generated); in each remaining
   line, collapse every run of whitespace to one space and trim; drop empty lines; join with `\n`.
5. **Compare.** SHA-256 of the normalised new text against SHA-256 of the normalised saved copy (always the saved
   copy the evidence used, never the previous day's fetch). Different hash = **changed**.
6. **What a change logs.** (a) a short line diff (`difflib`, lines removed `-` and added `+`, in order), cut to **at
   most 300 characters**: the full page is never stored; (b) **quote still present**, per cited line: yes if the
   cited line, whitespace-normalised as in rule 4, is a substring of the normalised new text, else no; (c) **number
   changed**, per cited line: "no" if the quote is still present; otherwise the new line most similar to the cited
   line (`difflib.SequenceMatcher` ratio ≥ 0.6) is compared by the set of numbers in it (digits, Devanagari digits
   read as 0–9, commas dropped): "yes" if the sets differ, "no" if equal; "unknown" if no line reaches 0.6.
   A URL's summary is the worst over its cited lines (quote present: no if any line is gone; number changed: yes
   if any is yes, else unknown if any is unknown, else no).
7. **Output.** `v2/radar/drift_2026-10.json`: one entry per run (IST date, UTC time, credits, complete, URLs
   checked / changed / failed / not checked) and per changed URL the fields of rule 6, plus the new hash. The page
   text itself is not committed.
8. **App.** The Field Report shows "Pages that changed": N of M changed (M = URLs fetched in the latest run), and
   for each changed page: quote still present yes/no, number changed yes/no/unknown.

## B. Radar skeptic

1. **What.** For each radar event (`events` in the radar file: distinct kind, effective date, set of states), **one**
   Tavily search, once per event, looking for a reversal of that price change.
2. **Query: model-written.** Nemotron (the small model, then the mid model if the small one fails, as in the
   four-arm test) is given the event's kind, states, effective date, change and the language of its first source
   page (`lang` of that card; `en` or `hi`), and asked for one search query, **in that language**, looking for news
   that the change was withdrawn, rolled back, stayed or postponed. Code checks it: a non-empty string of at most 300
   characters; otherwise the next model; if both fail, no search is sent and the event is marked "skeptic not run".
3. **Same time lock.** The radar's own window, `v2.rules.window("2026-10")` (21 Sep to 29 Oct), sent as
   `start_date` / `end_date`, with the radar corroboration settings (topic news, basic depth, `max_results` 10).
   Code then drops any result whose date (`shadow_cpi.tavily.best_date`) is missing or outside the window.
4. **Flag rule (code, not the model).** Results whose URL is one of the event's own sources are skipped. In each
   kept result's title and snippet (split into sentences at `.`, `!`, `?`, `।` and line breaks), the first sentence
   that contains a **reversal word** and a word of the event's kind (`v2.kinds`, whole words) is the quote. Reversal
   words, whole words, case-insensitive:
   - English: withdrawn, withdraw, withdraws, withdrew, rolled back, roll back, rolls back, rollback, stayed,
     stays, stay order, postponed, postpone, postpones, deferred, put on hold, reversed, revoked, scrapped.
   - Hindi: वापस, वापसी, रोक, स्थगित, टाला, टाली, टल.
   The event is **challenged** if any result yields a quote; the output is the URL and that exact sentence.
5. **What it changes: nothing.** The flag ("challenged: URL + quote") is shown beside the event on the radar page.
   It never changes tiers, effects, events, the freeze or the score.
6. **When and credits.** After the drift step in `tools/radar_daily.sh`, for every event that has no skeptic search
   yet, until the radar freeze (as A.2). Budget **`radar-skeptic-2026-10`**, cap **40** credits, read from
   `config/budget.json`; one search = 1 credit. Output: `v2/radar/skeptic_2026-10.json`.

## C. Leaks by source type (0 credits)

1. **Data.** Saved files only: `results/date_field_test.json` (date test, all arms A–D) and
   `results/finance_lookahead.json` (finance check, arms N and D). One unit = one result row of one arm of one case,
   as the existing metrics count results.
2. **Leak.** Date test: label `L` (Wayback-confirmed leak). Finance check: label `confirmed`. Unconfirmed labels
   (date test F/U; finance snippet/flag/none) count in the totals, not as leaks.
3. **Source type, from the URL only, first rule that matches wins** (lower-cased; path = URL path, query ignored):
   1. **live blog:** the path contains `live` as a whole token between `/`, `-`, `_` or `.`, or contains `liveblog`,
      `live-blog`, `live-updates` or `liveupdates`.
   2. **hub or tag page:** the path has no segment (site home page), or a segment is one of `tag`, `tags`, `topic`,
      `topics`, `category`, `categories`, `section`, `sections`, `hub`, `archive`, `archives`, `search`, `author`,
      `authors`, `latest`, `latest-news`, `keyword`, `keywords`, `page`; or the path ends with `/` and its last
      segment has no digit and at most one hyphen.
   3. **article:** the last non-empty segment has at least 3 hyphens, or the path contains a run of at least 6 digits,
      or a segment is `article`, `articles`, `articleshow`, `story` or `news` followed by a further segment.
   4. **other:** everything else (PDFs, government and company pages, ...).
4. **Table.** Per type: leaks, total results, leak rate with **Wilson 95%** (`v2.date_test.wilson`), by source file
   and pooled. Shown on the Field Report; a suggestion in `FEEDBACK_NOTES.md`. Exploratory: written after both
   tests were run and scored; it changes no verdict.
