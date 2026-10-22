# Instructions for Claude Code working on Shadow CPI

Hackathon track: **Best Apps and Agents** (not Personal AI). Bonus target: Best Use of Tavily.

The owner (Shweta) does not code. Explain results in plain English, show PASS/FAIL style summaries, and never print API key values (only variable names).

## Non-negotiable rules
1. **Tavily is the only way web data enters the system.** Use `shadow_cpi/tavily.py`. Direct downloads only as a logged fallback.
2. **Nemotron only extracts** (facts + exact quotes). **Code decides** every number. Never let a model choose a prediction, range or weight.
3. **Only verified evidence is used:** the model cites a numbered line (`verify.split_lines`), code takes that exact line and checks the number is in it (`nemotron._attach_lines` sets `verified`). Never let a model write a quote.
4. **Maths:** combine index LEVELS with official 2024-series weights (`cpi_math.aggregate`); never average percentage changes; compute YoY last; no rounding on the way. Tracked items move only their own weight (carve-out).
5. **Test months (Jan–Sep 2026) are never used to tune anything.** Calibrate only on 2025.
6. **All outside calls go through `Recorder`** (cache + flight recorder). Estimate Tavily credits before any batch run and stop if it would exceed the remaining balance.
7. Refuse to run with 2012-series weights (food weight ≈ 45.86% instead of ≈ 36.75%).
8. Keys live only in `.env` (git-ignored) or hosting secrets.

## Task protocol
1. One task at a time. If a long run is in the background, only do offline work (tests, code, docs) until it ends.
2. Before any run that can change a scored or sealed number: write the rule in the relevant pre-registration file and commit it with a timestamp first. State the commit in the report.
3. Build and test offline first (fake Tavily/Nemotron, 0 credits). Then do one real run under the task's credit cap. Hard caps in config/budget.json; stop cleanly at the cap and mark work incomplete instead of exceeding it.
4. Never edit results after seeing them, except logged bug fixes with scores before and after.
5. Every number shown in the app or docs must be read from a results file, never typed. If app and docs disagree, fix both in the same task. Exception: run-dependent counts in README/Devpost (calls, credits, % in window, latency) are not updated after each task; `python tools/sync_doc_numbers.py` fills them with an "as of" date in the Sunday consistency pass and again after the seal. Scored numbers from score_lock.json stay as they are.
6. Do not ask for, print or store API keys. Never enable paid usage or pay-as-you-go anywhere.
7. End every task with the REPORT format below, then stop and wait.
8. Matt Pocock skills (/implement, /tdd, /code-review, /to-tickets, /pr, /retro) run under these rules and the non-negotiable rules: one writer on main, hard credit caps, pre-register before scored runs, no parallel sub-agents that call Tavily or Nemotron, and end with the REPORT format. Never use /implement-spec on this repo.

REPORT format (keep it under 40 lines, plain English):
- DONE: one line on what changed, plus commit hashes
- DECISIONS NEEDED: at most 3, each with options and your recommended option first (or "none")
- NUMBERS: any number that changed, as old → new (source file)
- CREDITS: Tavily used this task / left above the reserve; Nemotron calls sent
- TESTS: count passing; key scan clean yes/no
- RULES: pre-registered before running? yes/no/not applicable
- DEVIATIONS: anything done differently from the task card, and why
- APP: what to look at on the live app, if anything changed
- NEXT: the obvious next task

## Build order
All build prompts are in **PROMPTS.md** in this folder (no sign-in needed). Prompt 0 is implemented as `checks.py`. Next: Prompt 1 (official data + baselines; files go in `data/official/`), Prompt 2 (evidence engine), Prompt T (Tavily at the centre), Prompt 3 (replay + go/no-go), Prompt 4 (app), Prompt 5 (seal), Prompt 6 (deploy).

## Scope (must / should / could)
- Must: checks, official data + baselines, government price spine, event layer, gold/silver observed, carve-out aggregation, 3-way replay, all web data via Tavily, Tavily attribution + report card, October seal, app (Home, Evidence, Scoreboard, Flight Recorder), README + video.
- Should: coverage meter, contributions, "Try to prove this wrong", reporter brief, pass-through ratio, Map/Crawl of official sites, evidence chasing, "Run now" with a daily cap.
- Could: map view, Hindi price quotes, online retail prices, mandi early warning, weekly automation.

Key dates: feature freeze 27 Oct; seal + submit 29 Oct (deadline 30 Oct 10:00 PT); October CPI release 12 Nov; judging 1–15 Dec (app must stay free and live); November CPI release scheduled 12 Dec (a Saturday, so likely Mon 14 Dec, still inside judging).

## Agent skills

### Issue tracker

Issues live in GitHub Issues on bhavikjain026/shadow-cpi, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
