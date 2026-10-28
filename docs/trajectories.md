# Leak-free research trajectories

`timelock/trajectories.py` turns the time lock into a small generator of research trajectories: the task, the cutoff,
every search the agent made, what the look-ahead check said about each result, what the as-of page check said about
each page, which results were kept (as-of verified or not checked) as evidence and why the rest were dropped. A SHA-256 "retrieval receipt" seals
the whole record. It costs 0 Tavily credits and 0 Nemotron calls when replayed from the cache.

**Not measured: we have not trained or evaluated any model on these.**

## Why

Search is moving from inference into training. Tavily describes NVIDIA post-training deep research agents on
trajectories that include real Tavily results: about 80,000 trajectories generated, about 67,000 kept after a judge
filtered them, used to fine-tune Nemotron 3 Super for AI-Q (Tavily,
[How NVIDIA Uses Tavily to Post-Train Deep Research Agents](https://www.tavily.com/blog/how-nvidia-uses-tavily-to-post-train-deep-research-agents);
NVIDIA's own write-up: [How NVIDIA AI-Q Reached #1 on DeepResearch Bench I and II](https://huggingface.co/blog/nvidia/how-nvidia-won-deepresearch-bench),
12 Mar 2026). Tavily's CEO, Rotem Weiss, makes the general case: teacher models answer hard questions with Tavily
Search, and the data keeps the whole research process, dead ends and reformulations included
([The Shift From Search at Inference to Search in Training](https://tavily.com/blog/the-shift-from-search-at-inference-to-search-in-training),
4 Sep 2026). All three links and figures checked on 2026-10-28; the figures are those posts' own.

A trajectory used for training or evaluation has a problem these posts do not discuss: if the question is "what will
happen after date X", any search result from after X gives the answer away. A model trained on such trajectories
learns to find the answer instead of reasoning towards it, and an evaluation scored on them overstates the model.
Our own measurements show how often this happens with ordinary search settings (TimeLock-34,
`benchmarks/timelock34/`). The time lock is the guard: every search is limited to the window ending on the cutoff,
every result is checked against every date we can see, and nothing dated after the cutoff can enter the kept evidence.
Kept evidence is reported in two groups, as-of verified and not checked, because a date alone does not prove a page's
text is from before the cutoff.

## Format (`timelock-trajectory/1`)

One JSON object per trajectory (see `examples/trajectories/*.json`):

| field | what it holds |
|---|---|
| `task` | the question (and, in the demo, which TimeLock-34 case it came from) |
| `cutoff` | ISO date; nothing after it may be used |
| `mode` | `replay` (cached responses), `live` or `custom` (caller's own search_fn) |
| `searches[]` | step, query, the parameters sent, the date window, Tavily's `request_id`, `response_sha256`, result count |
| `results[]` | per result: url, short title, Tavily date, address date, page date, the search_fn's own label (`search_label`, recorded but not trusted), our `verdict` (safe / date_flag / leak), `as_of`, the `extract` record, `decision`, `reason`, a short `quote` and where it came from (`quote_from`) |
| `results[].as_of` | `as-of verified (tavily_live)` or `as-of verified (wayback_asof)`: a copy of the page as of the cutoff was found. `not checked (no cached archive lookup)`: the Wayback lookup this check needs is not in the cache. Other `not checked (…)` reasons: Wayback lookup failed, Extract returned another address, page not read. `refused: no as-of copy`: the archive was checked and holds no copy from on or before the cutoff. `skipped`: the date check had already dropped the result |
| `results[].extract` | the `extract_as_of` record: status, reason, capture time, change signals, the live page's own date, and only the SHA-256 of any page text |
| `evidence.kept_as_of_verified[]` | kept, with a page copy as of the cutoff: url, quote, every date seen (all on or before the cutoff), `as_of`, why |
| `evidence.kept_not_checked[]` | kept on dates alone: same fields. **Snippet-level evidence**: the snippet is today's page, not checked as of the cutoff |
| `evidence.dropped[]` | url and the reason (leak, date_flag, or archive checked and no copy as of the cutoff) |
| `counts` | results, kept, kept_as_of_verified, kept_not_checked, dropped, and the verdict counts |
| `receipt` | `sha256` of the trajectory without the receipt (JSON, sorted keys, no spaces, UTF-8) |

No page text is stored. Quotes are at most 25 words: from the as-of copy when one was served, else the first sentence
of the snippet, else the title, as in `exports/evidence.csv`.

**The keep rule.** A result is kept only if `timelock.check_result` says *safe* for every date it can see: Tavily's
date, a date in the address, and the page's own date. The check is run again inside `generate()` on every result,
whatever the search function said. A final check refuses to return a trajectory whose kept evidence carries a date
after the cutoff.

**A page edited after the cutoff.** If the live page states a date after the cutoff but `extract_as_of` finds a
Wayback copy from on or before it, that copy is served, as in the library. The copy's own date is the one checked,
and the quote is taken from the copy. The result is kept as as-of verified. If no such copy exists, the result is
dropped.

**What "not checked" means.** A result under `kept_not_checked` is *dated* on or before the cutoff, but its snippet
comes from the page as it is today, so a page edited after the cutoff can still carry later text there.
`generate(..., require_as_of=True)` raises `AsOfNotChecked` instead of returning a trajectory with any such result.
It does not drop them quietly.

## Use it

```python
from timelock.trajectories import CachedTavily, generate, verify_receipt

task = {"question": "Did the RBI change the repo rate in October 2026?",
        "searches": [{"query": "RBI repo rate decision October 2026", "topic": "news", "max_results": 5}]}
traj = generate(task, "2026-10-06", client=CachedTavily("cache"))   # replay: 0 credits; CacheMiss if not saved
assert verify_receipt(traj)
```

- **Replay only in this version.** `generate()` takes a `CachedTavily` client (any other client raises `TypeError`)
  or the caller's own `search_fn`. No path in it calls Tavily or the Wayback Machine. A live mode would have to run
  through the repository's Recorder and budget caps (`shadow_cpi.budget.Budgeted`, `config/budget.json`). It is not
  built: adding a budget for it needs the owner's agreement.
- **Replays fail loudly.** `CachedTavily` serves only the exact request that was saved (Recorder cache key) and raises
  `CacheMiss` otherwise. For a single-page Extract it also serves that page's result out of a saved multi-page Extract
  call with the same other parameters (the date test extracted pages in batches; the earliest saved copy is used). The
  record keeps that call's `request_id`.
- **Wayback offline.** A Wayback lookup that is not in the cache is never fetched and never shown as "no archive
  copy". The result is marked `not checked (no cached archive lookup)` and, if kept, goes under `kept_not_checked`.

## The demo: five TimeLock-34 cases, replayed

```bash
python examples/trajectory_demo.py --cache ../shadow-cpi/cache          # writes examples/trajectories/*.json
python examples/trajectory_demo.py --cache ../shadow-cpi/cache --check  # exit 1 if they would change
```

Each case's time-locked search (the `dates_filter` arm: Tavily's date filter on, window ending on the cutoff) is
replayed from the cache. The replayed response's SHA-256 is checked against the case's own receipt in
`benchmarks/timelock34/cases.jsonl`. A case without cached data is skipped and named in
`examples/trajectories/index.json`. The counts below are written by the demo from the files it wrote; none is typed.

<!-- counts:begin (examples/trajectory_demo.py writes this block) -->
Of the 34 TimeLock-34 cases, 34 have their time-locked search in the cache. Written: E1, M3, T3, R5, C6 (5 trajectories); skipped for missing cached data: none. Across the 5: 19 results, 18 kept, 1 dropped (1 leak, 0 date_flag). **Only 1 of the 18 kept results has a page copy as of the cutoff (as-of verified); the other 17 are snippet-level evidence, not checked as of the cutoff.**
<!-- counts:end -->

**In plain words:** in this demo almost none of the kept evidence was checked as of the cutoff. The Wayback lookups
for those pages were never saved in the form `extract_as_of` reads, so the kept results are snippet-level evidence
dated on or before the cutoff, not pages verified as of it. In C6 (TCS Q2 FY27 results, cutoff 2026-10-07), one
result carries Tavily's date 2026-10-07 but states its own date as 2026-10-08. It is dropped as a leak, which
Tavily's date filter alone would have let through.

## Plugging in a Nemotron agent on Token Factory (described, not run)

This loop has not been run. Nothing below has been measured.

1. **Agent.** A Nemotron model on Nebius Token Factory (OpenAI-compatible chat completions, the same endpoint
   `shadow_cpi/nemotron.py` uses; model IDs by date in `config/models.json`). It is given the task, the cutoff and one
   tool, `search(query, **params)`.
2. **Tool.** The tool is `timelocked_search` on a Recorder-backed client, so every call stays inside the window,
   is logged in the flight recorder and is cached. The agent sees only what the time lock returns. Results labelled
   `leak` should be hidden from the model, not just labelled, so it cannot read them.
3. **Loop.** The model proposes a query; code runs it; the model reads the safe results and either searches again or
   answers. A step limit and the credit cap in `config/budget.json` bound the run.
4. **Seal.** After the run, pass the agent's queries as `task["searches"]` to `generate(task, cutoff,
   client=CachedTavily(cache))`. Each query hits the response the agent saw (same request, same cache key), so sealing
   costs 0 credits and the receipt covers exactly what the agent retrieved. The model's own reasoning text and answer
   would be stored next to the trajectory, not inside it. That keeps the receipt about retrieval.
5. **Use.** For evaluation, score the answer against what happened after the cutoff. For training, keep only
   trajectories whose receipt verifies and whose kept evidence passed the check. Under this repository's rules a model
   only extracts; using these as training data is outside what Shadow CPI itself does.

**Not measured: we have not trained or evaluated any model on these.**
