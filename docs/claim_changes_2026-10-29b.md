# Claim changes, 29 Oct 2026, card 2 (labels, attribution, feedback by product, seal scope, gallery)

Every changed claim, old → new, as edited in the source (templates for README/Devpost/gallery; numbers are placeholders and did not change). Test-file edits not listed. Also: `docs/gallery/1_leak_demo.png` rebuilt from the local app (new card label and "0 of 42 detected"); the five-question feedback block is new (`docs/templates/feedback_five.md`), rendered into Devpost and the FEEDBACK_NOTES summary.


## `app_pages/common.py`

| Old | New |
|---|---|
| searches each with and without Tavily's time lock, | searches each with and without the time lock (Tavily date filters), |

## `app_pages/field_report.py`

| Old | New |
|---|---|
| NO_DATES, TIME_LOCK = "No dates", "Tavily time lock" | NO_DATES, TIME_LOCK = "No dates", "Time lock (Tavily date filters)" |
| """Leak rate, no dates vs Tavily time lock (dates | """Leak rate, no dates vs the time lock (Tavily date filters: dates |
| the cutoff. Tavily time lock = start_date | the cutoff. Time lock (Tavily date filters) = start_date |
| cases): Tavily time lock {c['leak_cases']} of | cases): Time lock (Tavily date filters) {c['leak_cases']} of |
| ("Date test, Tavily time lock (dates + filter_by_published_date)", | ("Date test, Time lock (Tavily date filters): dates + filter_by_published_date", |
| ("Finance check, Tavily time lock", | ("Finance check, Time lock (Tavily date filters)", |
| . Bold = Tavily time lock | . Bold = Time lock (Tavily date filters) |
| no dates vs the Tavily time lock (dates + | no dates vs the time lock (Tavily date filters: dates + |

## `app_pages/leak_demo.py`

| Old | New |
|---|---|
| searched with no time lock and with Tavily's time lock. | searched with no time lock and with the time lock (Tavily date filters). |
| LOCKED, LOCKED_NOTE = "Tavily time lock", | LOCKED, LOCKED_NOTE = "Time lock (Tavily date filters)", |
| once with no date limits and once with Tavily's time lock, | once with no date limits and once with the time lock (Tavily date filters), |
| "Tavily time lock (pre-registered)": | "Time lock (Tavily date filters) (pre-registered)": |

## `app_pages/try_it.py`

| Old | New |
|---|---|
| LOCKED, LOCKED_NOTE = "Time lock", | LOCKED, LOCKED_NOTE = "Time lock (Tavily date filters)", |

## `shadow_cpi/leak_live.py`

| Old | New |
|---|---|
| (no time lock; Tavily's time lock) | (no time lock; the time lock, Tavily date filters) |
| no time lock, and Tavily's time lock. | no time lock, and the time lock (Tavily date filters). |

## `tools/build_leak_demo.py`

| Old | New |
|---|---|
| Tavily's time lock (start_date | the time lock, Tavily date filters (start_date |

## `tools/build_retry_table.py`

| Old | New |
|---|---|
| "locked": "Tavily time lock" | "locked": "time lock (tavily date filters)" |

## `docs/video_script.md`

| Old | New |
|---|---|
| With Tavily's time lock, every result was from before the cutoff. | With the time lock, Tavily's date filters, every result was from before the cutoff. |

## `app_pages/leak_demo.py`

| Old | New |
|---|---|
| "Time lock (Tavily date filters) (pre-registered)": | "Time lock (Tavily date filters), pre-registered": |
| f"Time lock, {AFTER_RETRY}": | f"Time lock (Tavily date filters), {AFTER_RETRY}": |
| st.metric(":green[Dates + time lock]: cases that leaked" | st.metric(":green[Time lock (Tavily date filters)]: cases that leaked" |

## `docs/templates/README.md`

| Old | New |
|---|---|
| did not exist). Separate rules; never added together. | did not exist). Explicit date windows already gave {{dt_datesonly}} of {{dt_cases}} detected (`start_date`/`end_date` only, Wilson {{dt_datesonly_w}}); the filter additionally drops undated pages (the dates-only search returned {{dt_undated_datesonly}} undated of {{dt_results_datesonly}} results here). Separate rules; never added together. |

## `docs/templates/devpost.md`

| Old | New |
|---|---|
| - **What a leak is.** | - **Dates or filter?** Explicit date windows already gave {{dt_datesonly}} of {{dt_cases}} detected (`start_date`/`end_date` only, Wilson {{dt_datesonly_w}}); the filter additionally drops undated pages (the dates-only search returned {{dt_undated_datesonly}} undated of {{dt_results_datesonly}} results here). - **What a leak is.** |

## `docs/templates/gallery.md`

| Old | New |
|---|---|
| `start_date`/`end_date` and `filter_by_published_date`, {{dt_dated}} of {{dt_cases}} ({{dt_dated_w}}). The cost: the | `start_date`/`end_date` and `filter_by_published_date`, {{dt_dated}} of {{dt_cases}} detected ({{dt_dated_w}}; the dates alone already gave {{dt_datesonly}} of {{dt_cases}} detected). The cost: the |
| {{rep_dated}} of {{rep_cases}} ({{rep_dated_w}}); pilot and replication together, same rule: {{pool_dated}} of {{pool_cases}} with dates + filter ({{pool_dated_w}}). Three cards (no dates, dates + time lock, | {{rep_dated}} of {{rep_cases}} detected ({{rep_dated_w}}); pilot and replication together, same rule: {{pool_dated}} of {{pool_cases}} detected with dates + filter ({{pool_dated_w}}). Three cards (no dates, time lock (Tavily date filters), |

## `tools/sync_doc_numbers.py`

| Old | New |
|---|---|
| out.append(f"\| {check}, {unit} \| {setting} \| | if setting.startswith("+ "): # cumulative arms: name every field sent setting = "start_date + end_date " + setting if "filter" in setting else \ "start_date + end_date + filter_by_published_date " + setting out.append(f"\| {check}, {unit} \| {setting} \| |

## `docs/templates/feedback_five.md`

| Old | New |
|---|---|
| - *Would we build with it again?* Yes: explicit date windows are what kept later articles out of a historical search, and every call returns a request ID we can cite. | - *Would we build with it again?* Yes: explicit date windows are what kept later articles out of a historical search, and the date fields held in every language we tried. |

## `tools/sync_doc_numbers.py`

| Old | New |
|---|---|
| return {k: str(v) for k, v in f.items()} def render( | f = {k: str(v) for k, v in f.items()} # the five-question feedback block (Devpost and the FEEDBACK_NOTES summary), rendered from the values above f["feedback_five"] = render((root / "docs/templates/feedback_five.md").read_text(encoding="utf-8"), f).rstrip("\n") return f def render( |

## `docs/templates/devpost.md`

| Old | New |
|---|---|
| ## Feedback for Nebius and NVIDIA (Token Factory, Nemotron Nano, Nemotron Super) **What each was used for.** *Nebius Token Factory* (`{{nebius_host}}`): the one OpenAI-compatible endpoint for every model call, through `shadow_cpi/nemotron.py`. *Nemotron Nano* (`{{nano_id}}`): the yes/no gatekeeper ("does this page state an Indian price or price change?") and display-only English glosses ({{nano_sent}} calls sent). *Nemotron Super* (`{{super_id}}`): reads each page as numbered lines and cites the line for every price and price change; writes the search fields in arms B, C and H ({{super_sent}} calls sent). **What worked well.** - JSON-schema output worked on the opening call (`checks.py`, "[PASS] Nemotron JSON output"), so every answer is parsed, not guessed. Every call sends `response_format` with a strict schema; a refusal falls back to JSON mode with the schema in the prompt (logged from {{migration_registered}}). Both of Nebius's replacement models accepted the same schema request in a smoke test on {{migration_registered}} (`results/model_migration_smoke.json`). - One endpoint for both sizes: the cheap gatekeeper and the careful reader are a config change apart (`config/models.json`). - Citing line numbers instead of copying text made Hindi pages work: the model returns a line number, code copies that line from the Extract output and checks the number is in it. **What needs work.** - Nano returned no number on pages where Super, re-reading the same page, found one: Super re-read {{nano_null_rereads}} pages and found a verified number on {{nano_null_found}}. A schema hint ("a number is required when the line has a currency or %"), or a confidence field, would help. - Nano, as gatekeeper, said "no" to a page that plainly listed rupee prices (a Delhi vegetable-price page); we added a code backstop so a page with a visible rupee price is never skipped. - Super sometimes labelled the item from the page's context rather than the cited line, and took the low end of a price range; code now requires the item name in the cited line. - Reliability: one read timeout and one connection reset each stopped a long run; our client now retries timeouts. The `/models` list mixes naming styles (case, `3.5` vs `3_5`), and a vision model sits next to the text models, so picking by name needs care. - Billing onboarding was confusing: the free trial, a separate promo balance and the 'paid usage after trial' switch were hard to tell apart, and with a card saved we couldn't be sure the card wouldn't be charged, so we kept paid usage off. **Onboarding, from zero to hello world.** Put the key in `.env`, point any OpenAI-compatible client at the endpoint, call `/models`, then one chat completion with a JSON schema: that is `checks.py`, and it passed on the opening call. The step that took care was choosing model IDs from the `/models` list. **Would we build with them again?** Yes: one endpoint with a small and a large model, strict JSON-schema output, and line-number citing let code, not the model, decide every number. We would ask for the fixes above. | ## Feedback by product: Nebius Token Factory, Nemotron Nano, Nemotron Super (and Tavily, separately) {{feedback_five}} |

## `docs/templates/feedback_summary.md`

| Old | New |
|---|---|
| ## Summary | ## Summary {{feedback_five}} **All entries** |

## `docs/templates/README.md`

| Old | New |
|---|---|
| 4. **The seal.** Canonical JSON, its `SHA-256`, and a git tag. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. | 4. **The seal.** Canonical JSON, its `SHA-256`, and a git tag. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. The seal proves when the forecast was committed, not what was read before it; the time lock and `extract_as_of` address the evidence. |
| compare it with `sealed/2026-10.sha256` ([`verify.md`](verify.md)). | compare it with `sealed/2026-10.sha256` ([`verify.md`](verify.md)). The seal shows when the forecast was committed; what the evidence could have seen is the time lock's job. |

## `docs/templates/devpost.md`

| Old | New |
|---|---|
| 4. **The seal:** canonical JSON + `SHA-256` + a git tag. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. | 4. **The seal:** canonical JSON + `SHA-256` + a git tag. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. The seal proves when the forecast was committed, not what was read before it; the time lock and `extract_as_of` address the evidence. |

## `verify.md`

| Old | New |
|---|---|
| The git tag `seal-<month>` and GitHub's own push record show **when** it was locked. | The git tag `seal-<month>` and GitHub's own push record show **when** it was locked. The seal proves when the forecast was committed, not what was read before it: the time lock (Tavily date filters, re-checked in code) and `extract_as_of` address the evidence. |

## `app_pages/home.py`

| Old | New |
|---|---|
| st.caption("Full steps: verify.md in the repository. Before the seal the links open once the tag exists.") | st.caption("The seal proves when the forecast was committed, not what was read before it; the time lock and " "extract_as_of address the evidence. Full steps: verify.md in the repository. Before the seal the links " "open once the tag exists.") |

## `drafts/judge_faq.md`

| Old | New |
|---|---|
| Then we show it. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. | Then we show it. We publish the prediction's SHA-256 and a Git tag before release, so anyone can verify the file they have. The seal proves when the forecast was committed, not what was read before it; the time lock and `extract_as_of` address the evidence. |

## `app_pages/research.py`

| Old | New |
|---|---|
| how to use the exports, as_of() and seal checks without look-ahead bias, | how to use the exports, as_of() and seal checks (which show when a forecast was committed) without look-ahead bias, |

## `docs/video_script.md`

| Old | New |
|---|---|
| we publish its SHA-256 and a Git tag before the twelfth of November release, so anyone can check i | we publish its SHA-256 and a Git tag before the twelfth of November release, so anyone can check when it was committed; the time lock is what guards the evidence. So anyone can check i |
| the time lock is what guards the evidence. So anyone can check it." | the time lock is what guards the evidence." |

## `docs/templates/README.md`

| Old | New |
|---|---|
| <details> <summary>Footnote: what counts as a leak, and the update after the archive retry</summary> | \| \| \| \|---\|---\| \| [![Leak demo, the app's opening screen: three result cards and the interval chart](docs/gallery/1_leak_demo.png)](docs/gallery/README.md#the-opening-screen) \| [![Field Report: who should write the search, four arms](docs/gallery/2_four_arm_table.png)](docs/gallery/README.md) \| \| [![The R196 timeline: Tavily date, cutoff, page edited, extract_as_of refuses](docs/gallery/3_r196_timeline.png)](docs/gallery/README.md) \| [![The pipeline: Tavily search, time lock, Extract, Nemotron quote check, seal](docs/gallery/4_flow.png)](docs/gallery/README.md) \| <details> <summary>Footnote: what counts as a leak, and the update after the archive retry</summary> |
| [![The R196 timeline: | [![The {{asof_row}} timeline: |

## `docs/templates/feedback_five.md`

| Old | New |
|---|---|
| Yes, as a cheap first filter, with the code backstop in place. | Yes, as a cheap gatekeeper, with the code backstop in place. |
