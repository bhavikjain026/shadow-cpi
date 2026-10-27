# timelock34: datasheet

34 replay questions with a cutoff date, the exact Tavily searches we ran for each, and a leak label for every result
URL those searches returned. Use it to measure whether a search setup returns pages that did not yet exist at the
cutoff (look-ahead leakage), and how much valid evidence it keeps while doing so.

Files: `cases.jsonl` (one case per line), `score.py` (scorer, standard library only), `build.py` (rebuilds
`cases.jsonl` from the committed results; `--check` fails if it would change). Built 27 Oct 2026; 0 Tavily credits
(everything comes from responses saved in October 2026).

## How it was built

Two experiments in this repository, each with its own pre-registration:

| Set | Cases | Questions | Pre-registration | Results file |
|---|---|---|---|---|
| `date_test` | 20 | Announced Indian price changes (milk, electricity, LPG, petrol/diesel, bus fares) in April–July and September 2026; cutoff = the replay cutoff for that month (the 29th) | [`v2/DATE_TEST_PREREG.md`](../../v2/DATE_TEST_PREREG.md) (pilot) | `results/date_field_test.json` |
| `finance` | 14 | Five RBI policy decisions and nine quarterly results (TCS, Reliance Industries, HDFC Bank, ICICI Bank, Infosys), February–October 2026; cutoff = the day before the event | [`v2/FINANCE_PREREG.md`](../../v2/FINANCE_PREREG.md) (exploratory) | `results/finance_lookahead.json` |

Two pairs of date-test cases (M8/M9, M11/M12) are two price changes in the same state and month, so they share a
question, a cutoff and the same searches; the experiment counted them as separate cases, and so does this dataset
(32 distinct questions).

Each case was searched with Tavily in several settings, run close together in a seeded random order with everything
else identical. The setting names are shared across both sets:

| Name in `cases.jsonl` | Date test arm | Finance arm | What was sent |
|---|---|---|---|
| `no_dates` | A | N | no dates, `filter_by_published_date=false` |
| `dates` | B | – | `start_date`/`end_date` (month start to cutoff), filter off |
| `dates_filter` | C | D | `start_date`/`end_date` + `filter_by_published_date=true` |
| `dates_filter_page_date` | D | – | C's results, kept only if the page's own date (Tavily Extract) is on or before the cutoff |

`requests` holds the exact request body of every search (rebuilt from the experiment code and checked equal to the
saved request for all 88 search arms, with the same result URLs in the same order); `receipts` holds Tavily's
`request_id` and the SHA-256 of each saved response, so the source responses can be identified.

## Labels

Every result URL has one `leak` label, from the experiment's own pre-registered rule, after the logged retry of
failed Wayback lookups (`results/*_wayback_retry.json`; the first pass is the pre-registered result, the retry only
recovers lookups that had failed, and left none failed):

| `leak` | Meaning | Date test source label | Finance source label |
|---|---|---|---|
| `confirmed` | The Wayback Machine has no capture on or before the cutoff and a date signal (Tavily's or the address's) is after it | `L` | `confirmed` (also: title + snippet state the outcome) |
| `date_flag` | A date signal is after the cutoff, not confirmed by Wayback | `F` | `snippet`, `flag` |
| `unknown` | No date signal after the cutoff | `P`, `U` | `valid`, `none` |

`source_label` keeps the original label. `valid_evidence` is true for a page that Wayback shows existed on or before
the cutoff and that is on topic (date test: label `P` and the item named in the title or snippet; finance: label
`valid`, the company or RBI named). Other fields per result: `published_date` (Tavily's, ISO), `url_date` (a
`/YYYY/MM/DD/` date in the address), `page_date` (explicit published/updated date on the page, date test arm D only),
`wayback_captures` (capture dates; `null` = lookup failed), `states_outcome` (finance only), and `quote`.

**No page text.** `quote` is at most 25 words: for finance results, the first snippet sentence that matches the
pre-registered outcome rule; otherwise the page title. It identifies the page; it is not evidence on its own.

## Scoring

```python
from benchmarks.timelock34.score import score
s = score(lambda question, cutoff: my_search(question, cutoff))   # results with a 'url', or URLs; None skips a case
s["all"]["leak_cases"], s["all"]["wilson95"], s["all"]["valid_kept"], s["all"]["valid_total"], s["all"]["unlabelled"]
```

A leak case is a case where at least one returned URL is labelled `confirmed`; the rate comes with a Wilson 95%
interval. Valid evidence kept = returned URLs with `valid_evidence` / all such URLs in the case. `python
benchmarks/timelock34/score.py` replays the recorded settings offline; it reproduces the after-retry numbers in
the two retry files (leak cases, and valid evidence lost = total − kept).

## Independent second review (AI-assisted, ChatGPT agent)

`second_review_chatgpt.csv` is a second, independent label for every result URL (283 rows; `R001` is the first
result of the first case in `cases.jsonl`, in that order). It was done by a ChatGPT agent, not by a person, and is
kept as received: a short quote (at most 14 words, from the page), the date relied on and its source, and a reason.
`compare_review.py` joins it to our labels (it refuses to run if a row's case or URL differs) and writes
`results/timelock34_second_review.json`.

The two reviews define a leak differently:
- **ours:** a result dated after the cutoff (`confirmed` when the Wayback Machine also has no capture by then);
- **the reviewer's:** content that reveals the outcome.

The reviewer decided 137 of 283 rows (LEAK or SAFE); 146 are UNCLEAR, because the live page would not open and
archive lookups were rate-limited. On the 137 decided rows:

| Our leak = | Agreement | Cohen's kappa |
|---|---|---|
| `confirmed` or `date_flag` | 89.1% | 0.76 |
| `confirmed` only | 75.9% | 0.36 |

Cases with at least one leak, by setting (reviewer vs ours, `confirmed`):

| Set | Setting | Reviewer | Ours |
|---|---|---|---|
| date test | `no_dates` | 4 | 10 |
| date test | `dates`, `dates_filter`, `dates_filter_page_date` | 0 | 0 |
| finance | `no_dates` | 14 | 10 |
| finance | `dates_filter` | 1 | 0 |

The date-test gap is mostly the definitions: every date-test row we label a leak that the reviewer called SAFE (9)
is a post-cutoff page on another topic, which reveals nothing, and 17 more were UNCLEAR. The finance gap goes the
other way: 3 rows with no date signal after the cutoff were judged LEAK because the page states the result.

**Filtered search, finance:** 0 of 14 filtered searches returned a result dated after the cutoff; an independent
reviewer found 1 page whose current version leaks the outcome (`R196`, a TCS results preview first published
7 Jul 2026, the day before the 8 Jul cutoff, and updated 9 Jul with a link to the actual result). Search filters by
date; Extract reads the page as it is today. Our published labels are not changed.

## Limits

- **Small.** 34 cases; one setting with 0 leak cases still has an upper 95% bound of about 10% (all 34) or 16–22%
  (one set). The date test is a pilot; the finance check is exploratory.
- **Labels exist only for URLs we saw.** A live search returns other URLs; `score.py` counts them as `unlabelled`,
  never as safe. Scoring a new search setup properly needs Wayback lookups for its new URLs.
- **Wayback is incomplete evidence.** A capture after the cutoff does not prove the page was published after it
  (it may simply not have been archived earlier); `confirmed` also needs a date signal after the cutoff, so it is
  conservative, and `date_flag` holds the uncertain rest. `unknown` is not "safe".
- **`url_date` can't read /2026/Oct/05/-style dates.** It reads only numeric address dates (`/2026/10/05/`,
  `2026-10-05`), so a month-name date in the address (newindianexpress.com uses `/2026/Oct/05/`) is not a date
  signal. A page whose only post-cutoff date is written that way gets `date_flag` or `unknown` instead of
  `confirmed`, and the labels here undercount for those pages. Left as is because changing it would change labels
  behind numbers already published.
- **`page_date` can pick up a date from the body, not the page's own.** The reader (`timelock.dates.page_date`)
  accepts "published"/"updated" + a date anywhere in the extracted text. On `R010` (a BNEF PDF) it read 2025-11-03
  from a citation ("Climatescope 2025 … published on Nov. 3, 2025"); the cover says 2026-10-13. On `R020` (an ITIF
  report) it read 2026-04-15 from a footnote ("… updated April 15, 2026"); the page says 2026-10-13. Both rows are
  still `confirmed` from Tavily's date and the Wayback captures, so their labels are right; but a wrong page date
  can let a post-cutoff page through the `dates_filter_page_date` setting. Labels left as published.
- **The second review used a different leak definition** and is AI-assisted; 146 of its 283 rows are UNCLEAR. It
  is a cross-check, not ground truth.
- **India, 2026, English-language news**, Tavily `topic=news`, `search_depth=basic`. Batch dates and Tavily's
  behaviour drift; results may differ when re-run.
- **Questions are tied to our own pipeline** (CPI items, a fixed event list); no question was tuned on these
  results.

## License

Our labels, the case list and the request bodies: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), credit
"Shadow CPI timelock34". The code (`build.py`, `score.py`) is under the repository's MIT license. URLs, titles and
the short quotes belong to their publishers and are included only to identify each page.
