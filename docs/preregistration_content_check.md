# Content-level leak check with Nemotron: pre-registration

**Written 2026-10-29, committed before any code for this check and before any Nebius call.** Decided by the owner.
**Exploratory and descriptive, added after scoring.** It cannot change any headline, scored verdict, rule, lock,
seal, earlier check or existing page. Its output is a list for the owner's hand review, not a leak rate. The rules
below are not changed after results are seen; a bug fix is logged here with the numbers before and after.

Code (written after this commit): `tools/content_check.py`; tests `tests/test_content_check.py`. Output:
`results/content_check.json`. New files only. 0 Tavily credits: the check reads saved excerpts and never calls
Tavily. At most 120 Nebius calls.

## Purpose
The date checks so far look at dates (Tavily's field, Wayback captures, explicit dates in page text). A page can
state an outcome without carrying a later date. This check asks a language model to read the saved excerpt itself
and say whether it states or clearly implies the outcome, or any other fact from after the cutoff. It is a second
lens on the same pages, nothing more.

## Inputs (saved files only)
- **Pilot**: `results/date_field_test.json`, the 20 date-test cases. Arm **C** (time-locked: start/end dates plus
  `filter_by_published_date`) is the object of study. Arm **A** (no dates) is the positive control.
- **Replication**: `results/replication.json`, the 22 price cases, same two arms.
- One unit = one saved result (case, arm, URL). Its text is the saved `content` excerpt of that result. Nothing is
  fetched. A unit with no saved excerpt is **not checked (no excerpt)** and counted so.
- Question = the case's `query`. Cutoff = the case's `cutoff`.
- Arms B and D are out of scope.

## Method
- Model: Nemotron Nano, role `small`, through the existing `shadow_cpi.nemotron.Nemotron` client (Token Factory,
  temperature 0, thinking off, JSON-schema output) and the dated model map (`shadow_cpi/model_map.py`; before
  2026-11-09 IST the call uses the original ID, after it the replacement). The model ID of each call is written to
  the result. The model is not told the arm.
- Prompt, per excerpt: *Given the question and the cutoff date, does this text state or clearly imply the outcome,
  or any fact from after the cutoff? Answer yes or no, and give the exact sentence.* The excerpt is sent as data,
  with the instruction that it is never a command.
- Output schema: `answer` (yes or no) and `sentence` (text or null).
- **Code check on the quote.** A "yes" counts as **flagged** only if the quoted sentence is really in the excerpt
  (compared after collapsing whitespace, case kept, ellipsis marks ignored at the edges). Otherwise it counts as
  "no" and the raw answer is kept in the file with the reason `quote not in excerpt`. A "yes" with no sentence is
  also "no". The model never decides a count; code does.
- A request that fails (transport error, unparseable answer) is retried once; if it fails again the unit is
  **not checked (error)**.

## Budget and sampling
- The saved population (distinct question + cutoff + excerpt requests) is larger than the Nebius cap, so the check
  **samples**. The cap is enforced in code on the transport: every attempt, retries included, counts, and the
  120th is the last. At the cap the run stops cleanly and the remaining units are **not checked (cap)**.
- Sample: **55 units per arm**, drawn with `random.Random(20261029)` without replacement from that arm's units
  (sorted by source, case id, URL), leaving ten attempts of slack for retries. Equal sizes make the two arms
  comparable. A request identical across two sampled units is sent once and applies to both.
- Units not drawn are reported as **not sampled**, separately from the not-checked counts.

## Outputs
- `results/content_check.json`: per unit the source, case, arm, URL, cutoff, question, flagged (true or false),
  the quoted sentence, the model ID, the raw answer, the reason a "yes" was dropped if it was, and the request
  receipt (flight-recorder call id, Nebius response id when present, SHA-256 of the response). Plus per-arm counts:
  checked, flagged, not checked (no excerpt, cap, error), not sampled, and the Nebius calls used.
- Reported: arm C flagged x of n checked; arm A flagged y of m checked. The positive control is expected to flag
  more. If it does not, the check is reported as uninformative, not as evidence about arm C.

## Hand labelling
Every flagged item is then labelled by the owner as true positive or false positive from the sentence and its
page. Only labelled items carry meaning; the raw flag counts are not leak rates, carry no confidence interval, and
are not quoted in the app, README or Devpost.

## Limits (stated now)
- A small model reading snippets: it can miss an implied outcome and can flag background that happens to be later.
- Snippets are the pieces Tavily returned, not whole pages.
- A sample of each arm, not the whole saved set.
- The model may know events from its training data; the quote check limits that to text really on the page.
