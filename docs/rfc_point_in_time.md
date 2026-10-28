# RFC: point-in-time retrieval for the Tavily API

Status: proposal, written as feedback to the Tavily team. Docs only; no Tavily credits were spent writing it.
Tavily docs and changelog checked on 2026-10-28.

## Why this, and why now

On 4 Sep 2026, Tavily's CEO Rotem Weiss wrote in
[The Shift From Search at Inference to Search in Training](https://www.tavily.com/blog/the-shift-from-search-at-inference-to-search-in-training):

> "If two model checkpoints are evaluated against different versions of the web, are the results comparable?"

and named the missing piece as

> "a snapshot or replay layer that preserves specific retrieval states for evaluation, debugging, or future training."

Shadow CPI is a small, concrete instance of that problem. We replay past months of Indian CPI and ask the system to
forecast each one using only what the web said before a cutoff date. If retrieval can see past the cutoff, the
forecast is contaminated and the score means nothing.

**The short version: it works today if you set it right.** `start_date` / `end_date` with
`filter_by_published_date: true` kept post-cutoff pages out of every arm we tested that used them (see
[`results/date_field_test.md`](../results/date_field_test.md),
[`results/finance_lookahead.md`](../results/finance_lookahead.md) and
[`results/lang_date_test.md`](../results/lang_date_test.md)). What it took to get there is a small library,
[`timelock/`](../timelock/__init__.py), that wraps Search and Extract with date checks, an archive fallback and
response hashes. Each proposal below is one piece of that library that could move into the API, so that every
caller gets it by default instead of rebuilding it.

All five proposals are additive: a caller who sends none of the new parameters gets exactly today's behaviour.

## Summary

| | Proposal | New request field | New response field(s) | Default |
| --- | --- | --- | --- | --- |
| a | Say how sure the date is, and where it came from | none | `published_date_confidence`, `date_source` | fields present, behaviour unchanged |
| b | Split original publication from last change | `date_filter_field` | `published_date_original`, `last_modified` | filter keeps today's meaning |
| c | Make the undated policy explicit | `undated` | `undated` echo, per-result `date_flag` | today's implicit policy |
| d | Say when the copy was fetched, and bound it | `content_as_of` | `fetched_at` per result | unset = today |
| e | Return the copy as it was on a date, with a receipt | `as_of`, `receipt` | `as_of_source`, `capture_time`, `receipt` | unset = live copy, no receipt |

---

## a) Per-result `published_date_confidence` and `date_source`

**Problem.** Tavily documents `published_date` as its "best estimate of when the source was published or last
updated" ([Search API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)). A
time-locked caller has to decide per result whether to trust that estimate, but the response gives no hint of how it
was made. A date read from `<meta property="article:published_time">` and a date guessed from body text look
identical. So we read the page ourselves, and our reader is the weak link: it only understands English and Hindi
date words, and an undated-by-our-reader page is not the same as an undated page.

**Evidence from this repo.**
- [`results/date_field_test.md`](../results/date_field_test.md), arm D and its addendum: adding our own page-date
  check on top of Tavily's filter mostly removed results whose page date we could not read, and much of what it
  removed was archive-confirmed as valid evidence from before the cutoff.
- [`results/lang_date_test.md`](../results/lang_date_test.md), "D results with no readable page date" by language:
  for Marathi and Tamil this measures our reader as much as the page, as the file itself says.
- The reader: [`timelock/dates.py`](../timelock/dates.py) (`page_date`, `DATE_WORDS`).

**Proposed fields.** Two per-result fields, no new request parameter.

```json
{
  "url": "https://example.com/news/2026/07/rate-decision",
  "published_date": "2026-07-07",
  "published_date_confidence": "high",
  "date_source": "meta"
}
```

- `date_source`: `"meta"` (structured page metadata: `article:published_time`, JSON-LD `datePublished`, etc.),
  `"url"` (a date in the address), `"sitemap"` (the site's sitemap `lastmod` / news sitemap), `"inferred"` (body
  text, crawl history or another heuristic), or `null` when there is no date.
- `published_date_confidence`: `"high" | "medium" | "low"` (or a 0–1 number; the labels are enough for a filter).

**Backward-compatible default.** Both fields are added to every result; nothing is filtered differently. Callers that
ignore them see no change. A later, opt-in `min_date_confidence` request field could let the date filter skip
low-confidence dates, but that is not needed for this proposal.

**What timelock does today.** [`timelock/check.py`](../timelock/check.py) treats Tavily's date, a date in the
address ([`url_date`](../timelock/dates.py)) and the page's own published/updated date as separate signals; any
signal after the cutoff makes the result a `leak`, and no signal at all makes it a `date_flag`. That needs
`include_raw_content` (larger responses) and our own regex reader. With `date_source`, a caller could trust `meta`
dates and only re-check `inferred` ones.

---

## b) Separate `published_date` and `last_modified`

**Problem.** Because `published_date` means "published or last updated", and the reference adds that it "can be later
than the original publish date", one field carries two different facts. For a point-in-time caller they point in
opposite directions: the original date says *when the page entered the world* (is it allowed at all?), the
last-modified date says *whether the copy you are reading has changed since* (is this text the cutoff's text?). A
page originally published before the cutoff and edited after it is the dangerous case, and today it is either filtered
out (losing valid evidence) or kept with no hint that the text moved.

**Evidence from this repo.**
- [`docs/tavily_bug_reports.md`](tavily_bug_reports.md), item 4 (code comparison of Tavily's date and the page's own
  date on the date-test pages; data in [`results/date_field_test.json`](../results/date_field_test.json)).
- Item 3 in the same file: a page Tavily dated before the cutoff whose current version links the outcome, because it
  was updated after the cutoff ([`results/timelock34_second_review.json`](../results/timelock34_second_review.json),
  `finance_filtered.example`).
- Repro: [`repro/published_vs_modified.py`](../repro/published_vs_modified.py) (prints both dates side by side).

**Proposed fields.**

Request:

```json
{
  "query": "RBI repo rate decision",
  "start_date": "2026-06-08",
  "end_date": "2026-07-07",
  "filter_by_published_date": true,
  "date_filter_field": "original"
}
```

Response, per result:

```json
{
  "url": "https://example.com/policy/repo-rate",
  "published_date": "2026-07-09",
  "published_date_original": "2026-07-07",
  "last_modified": "2026-07-09"
}
```

- `published_date_original`: the date the page was originally published, or `null` if unknown.
- `last_modified`: the most recent change Tavily knows of (page metadata, `Last-Modified` header, sitemap `lastmod`,
  or a content change between crawls), or `null`.
- `date_filter_field`: `"published_date"` (today's combined field), `"original"`, or `"last_modified"`.

**Backward-compatible default.** `published_date` keeps its current meaning and `date_filter_field` defaults to
`"published_date"`, so filtering is unchanged unless the caller asks. A point-in-time caller would filter on
`"original"` and then treat `last_modified > cutoff` as "fetch the archived copy" (see e).

**What timelock does today.** [`timelock/dates.py`](../timelock/dates.py) `page_date` reads both "published" and
"updated" from the page text and keeps the later one, so an edit after the cutoff is caught as a date signal.
[`timelock/asof.py`](../timelock/asof.py) `change_signals` then decides whether the live copy can be used, using the
page date plus the Wayback Machine's capture list (whether captures after the cutoff differ from the last one before
it). That is a second, outside service doing what a `last_modified` field would say directly.

---

## c) An explicit undated policy: `"keep" | "drop" | "flag"`

**Problem.** What happens to a result with no date is an important choice for a point-in-time caller, and today it
is implicit. The reference says that with `filter_by_published_date`, "results with no detectable published date are
also removed". Without the filter, undated results come back mixed with dated ones. Neither is wrong, but the policy
is tied to another switch, isn't echoed in the response, and gives no count of what was removed. A caller can't tell
"nothing undated matched" from "undated results were dropped".

For us, dropping is the safe default, but it is not free: the date tests above show that removing results without a
readable date also removes valid evidence. A caller who wants to review undated results (e.g. to check them against
an archive) currently has to turn the filter off and lose the date window too.

**Evidence from this repo.**
- The "Undated" columns in [`results/finance_lookahead.md`](../results/finance_lookahead.md) and
  [`results/date_field_test.md`](../results/date_field_test.md): undated results appear in the arms without the
  filter and not in the arms with it, as documented.
- The undated share across all our searches, in [`results/tavily_report_card.md`](../results/tavily_report_card.md)
  ("Search results inside the requested date window").
- [`docs/tavily_bug_reports.md`](tavily_bug_reports.md), item 1: undated results among the `auto_parameters`
  searches, where the window was not ours.

**Proposed fields.**

Request:

```json
{
  "query": "Amul milk price revision",
  "start_date": "2026-05-01",
  "end_date": "2026-05-31",
  "filter_by_published_date": true,
  "undated": "flag"
}
```

Response:

```json
{
  "undated": { "policy": "flag", "count": 2 },
  "results": [
    { "url": "https://example.com/a", "published_date": "2026-05-12", "date_flag": null },
    { "url": "https://example.com/b", "published_date": null, "date_flag": "undated" }
  ]
}
```

- `"keep"`: undated results are returned like dated ones.
- `"drop"`: undated results are removed; the response still reports how many (`undated.count`).
- `"flag"`: undated results are returned with `date_flag: "undated"`, so the caller can check them another way.

**Backward-compatible default.** When `undated` is not sent, behaviour is today's: `"drop"` when
`filter_by_published_date` is true, `"keep"` otherwise. The only change a current caller sees is the `undated` echo
object, which is new and can be ignored.

**What timelock does today.** [`timelock/search.py`](../timelock/search.py) always sends
`filter_by_published_date: true`, so Tavily drops undated results. For responses produced any other way (a saved
replay, a caller's own client), [`timelock/check.py`](../timelock/check.py) labels an undated result `date_flag`,
not `leak` ("undated pages are flagged, not rejected"), and the LangChain wrapper
([`timelock/langchain.py`](../timelock/langchain.py)) returns only `safe` results with counts of what it held back.
That is the `"flag"` policy, built on the caller's side.

---

## d) `fetched_at` per result, and a `content_as_of` bound on the cache

**Problem.** Search and Extract return Tavily's copy of a page, but not *when* that copy was fetched. The date filter
works on the page's date; the text comes from whenever Tavily last fetched it. So a page dated before the cutoff can
arrive with text added after it, and the response gives no way to see that.

Tavily already exposes the cache age on one side. The October 2026 changelog entry "Content freshness for Search"
([docs.tavily.com/changelog](https://docs.tavily.com/changelog), checked 2026-10-28) adds `max_age_hours`, which
"sets the maximum age in hours of Tavily's cached copy of each result", accepting `1` to `720`, `0` to always fetch
live, or `-1` to never fetch live. That bounds the copy from *below* (no older than N hours), which is the right tool
for prices and live scores. A point-in-time caller needs the opposite bound: no *newer* than a date.

**Evidence from this repo.**
- [`docs/tavily_bug_reports.md`](tavily_bug_reports.md), item 3 ("Extract has no as-of view, so Search dates do not
  freeze page content"), with request ID and response hash.
- Repro: [`repro/extract_no_asof.py`](../repro/extract_no_asof.py) (shows that no as-of or crawl-date field comes
  back).
- [`results/asof_demo_served.json`](../results/asof_demo_served.json): a page whose live copy and as-of copy differ,
  and which dates each copy contains (`live.post_cutoff_dates` vs `as_of.post_cutoff_dates`).

**Proposed fields.**

Request (Search, and the same field on Extract):

```json
{
  "query": "IOCL LPG cylinder price",
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "filter_by_published_date": true,
  "content_as_of": "2026-06-30"
}
```

Response, per result:

```json
{
  "url": "https://example.com/lpg-price",
  "published_date": "2026-06-14",
  "fetched_at": "2026-06-28T04:12:09Z",
  "content": "..."
}
```

- `fetched_at` (UTC timestamp): when Tavily fetched the copy whose text is in `content` / `raw_content`.
- `content_as_of` (ISO date): return only text from a copy fetched on or before this date. If Tavily has none, the
  result is either omitted or returned without text and with `fetched_at: null` (see e for the archive option).
  Combined with `max_age_hours`, the two give a fetch window: no older than N hours *before* `content_as_of`.

**Backward-compatible default.** `fetched_at` is added to every result and changes nothing. `content_as_of` unset
means today's behaviour. `max_age_hours` keeps its meaning; when both are sent, `max_age_hours` would be measured back
from `content_as_of` instead of from now, which should be stated in the docs.

**What timelock does today.** Nothing in the response tells us when the copy was fetched, so timelock records when
*it* made the call ([`timelock/asof.py`](../timelock/asof.py) stamps `capture_time` for a live copy with the call
time) and decides from outside evidence whether the live text is the cutoff's text: the page's own dates and the
Wayback Machine's capture list. When those disagree or are missing, it refuses the live copy rather than guess.

---

## e) Archive fallback (latest copy on or before the cutoff) and a signed retrieval receipt

**Problem.** Two parts, one goal: being able to show later exactly what retrieval returned for a past date.

1. *Fallback.* When the live copy may have changed since the cutoff, a point-in-time caller wants the latest copy
   Tavily holds from on or before the cutoff, or a clear "no such copy". Today the only route is an outside archive,
   which adds a second dependency, a second rate limit and a second set of failures (our date tests needed a network
   retry pass for archive lookups; see the "Network retry" sections of
   [`results/date_field_test.md`](../results/date_field_test.md) and
   [`results/finance_lookahead.md`](../results/finance_lookahead.md)).
2. *Receipt.* The CEO's question about comparing checkpoints is a question about provenance: two evaluations are
   comparable only if you can show they saw the same retrieval state. A `request_id` lets Tavily support look a call
   up; it does not let a third party check that a saved response is the one Tavily sent.

**Evidence from this repo.**
- The fallback, end to end: [`timelock/asof.py`](../timelock/asof.py) `extract_as_of`, with one refusal case
  ([`results/asof_demo_r196.json`](../results/asof_demo_r196.json)) and one served case
  ([`results/asof_demo_served.json`](../results/asof_demo_served.json)).
- Receipts we keep ourselves: `response_sha256` on every search ([`timelock/search.py`](../timelock/search.py)),
  per-call records in [`results/call_receipts.json`](../results/call_receipts.json), and the chain of custody in
  [`results/custody.json`](../results/custody.json). These are self-attested: they prove we did not change a
  response after saving it, not that Tavily sent it.

**Proposed fields.**

Request (Extract; the same two fields on Search would apply per result):

```json
{
  "urls": ["https://example.com/policy/repo-rate"],
  "as_of": "2026-07-07",
  "receipt": true
}
```

Response:

```json
{
  "results": [
    {
      "url": "https://example.com/policy/repo-rate",
      "raw_content": "...",
      "as_of_source": "tavily_archive",
      "capture_time": "2026-07-05T11:40:02Z"
    }
  ],
  "failed_results": [
    { "url": "https://example.com/other", "error": "no_copy_on_or_before_as_of" }
  ],
  "request_id": "…",
  "receipt": {
    "alg": "ed25519",
    "key_id": "tavily-receipts-2026",
    "issued_at": "2026-10-28T17:40:11Z",
    "request_sha256": "…",
    "response_sha256": "…",
    "signature": "…"
  }
}
```

- `as_of` (ISO date): return the latest copy Tavily holds that was fetched on or before this date.
  `as_of_source` says which: `"live"` (the current copy, and Tavily knows it has not changed since `as_of`),
  `"tavily_archive"` (an older copy from Tavily's own store), or the URL goes to `failed_results` with
  `no_copy_on_or_before_as_of`. It never silently falls back to the live copy.
- `receipt: true`: Tavily signs a hash of the canonical request and of the response body (results, dates, text) with
  a published key. Anyone holding the saved response and the public key can check it later, without calling Tavily.
  This is the "snapshot or replay layer" in its smallest form: the snapshot is the caller's, the proof is Tavily's.

**Backward-compatible default.** `as_of` unset returns the live copy as today. `receipt` unset adds nothing to the
response. Hash canonicalisation (key order, whitespace, encoding) needs to be specified once in the docs; we use
sorted keys, no spaces, UTF-8 ([`timelock/search.py`](../timelock/search.py) `response_sha256`).

**What timelock does today.** `extract_as_of` extracts the live page, checks change signals, and serves the live copy
only when nothing says it changed; otherwise it fetches the latest Wayback Machine capture on or before the cutoff,
checks that the archive served a capture from on or before it, and otherwise returns no text with the reason
`no as-of copy`. Every search result carries `request_id` and our `response_sha256`. A native `as_of` would remove
the archive dependency; a signed receipt would turn our hashes from "we say so" into "Tavily says so".

---

## Open questions for Tavily

1. **Do old cached versions exist?** When a page is re-fetched, is the previous copy kept, and for how long? (This
   decides whether `as_of` in e can be served from Tavily's own store or needs a new snapshot pipeline.)
2. Is a fetch time already stored per cached copy, so that `fetched_at` in d is a matter of returning it?
3. How is `published_date` produced today? Which sources are used, in what order, and is the source recorded
   anywhere that could become `date_source` (a)?
4. Is the original publication date ever kept separately from the last-updated date internally (b)?
5. With `filter_by_published_date`, is "no detectable published date" decided before or after the window check, and
   could the count of removed undated results be returned cheaply (c)?
6. How does `max_age_hours` relate to the copy Extract returns for the same URL? Does Extract have its own cache age,
   and would `content_as_of` belong on both endpoints (d)?
7. Would a signed receipt need to cover `raw_content`, or is a hash of the returned fields enough? Is there an
   existing key-publication channel (e)?
8. Would any of this change credit cost? For a point-in-time caller, an older cached copy is the cheaper answer, not
   the dearer one.

## What we did NOT measure

- **Recall under these proposals.** None of the fields exist, so we cannot say how much valid evidence they would
  keep that today's filter drops.
- **How often Tavily's cached copy itself post-dates a cutoff.** Without `fetched_at`, we only see the copy's dates
  and the archive's captures, never Tavily's own fetch time.
- **Date accuracy at scale.** Our date tests are pilots on hand-built case lists (see each results file for its size
  and confidence intervals), in one country and four languages, mostly Indian news and government pages.
- **Other search providers.** This RFC makes no comparison with any other provider.
- **Cost or latency of the proposed features.** Any figures here would be guesses.
- **Whether the issues still hold today.** Each item in [`docs/tavily_bug_reports.md`](tavily_bug_reports.md) records
  its own re-check date and outcome; Tavily's index and pages change, and our numbers are as measured on their dates.
