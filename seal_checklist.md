# October 2026 seal checklist

Seal date: **Thu 29 Oct 2026**, evidence cutoff **28 Oct 2026, 23:59 IST (18:29 UTC)**. Official release: 12 Nov 2026.
Seals run on `main`. The rules are frozen (`docs/frozen_rules.md`, `docs/preregistration.md`): nothing below
changes a rule, factor or filter.

## 1. Before 28 Oct (owner)
- [ ] Check the Tavily balance against `config/budget.json`. October's run is capped by `live-month` (120 credits)
      and `skeptic`. The ledger (`results/credit_ledger.jsonl`) is the source of truth, because Tavily's usage page
      does not update.
- [ ] **Spine for October, by hand:** run `.venv/bin/python tools/fetch_doca.py`, with a new chunk for Jan–Oct 2026
      and all 19 commodities. You type the CAPTCHA; the script never reads it. Then rebuild `data/spine.csv`
      (`python -c "from shadow_cpi import spine; spine.build()"`). October is a partial month (data up to the
      fetch date); note the fetch date.

## 2. On 28–29 Oct (evidence up to the cutoff)
- [ ] **IOCL LPG list:** re-extract `https://iocl.com/indane-14Kg-nonsubsid-previous-price` after 28 Oct.
      Amendment 1 (a) records October as an LPG **gap** if the saved list was fetched before the month's data.
      The current copy is from 20 Oct.
- [ ] **PPAC petrol:** re-extract `https://ppac.gov.in/archives/impnews` for October's Delhi petrol prices.
- [ ] **IBJA:** gold and silver reports up to 28 Oct (`ibja_daily` covers October automatically).
- [ ] **Evidence run for October:** quotes for **all** tracked items (a live month: cut 2 does not apply), events
      with the 10-day pre-window, and the new fuel kind only if PPAC lacks October. Hard caps apply.
- [ ] **Build `results/nowcast_2026-10.json`** with model (c) (`shadow_cpi.predict`). It needs:
      - `headline_yoy`;
      - the 80% range from **all 9** replay misses (prediction −0.14 / +0.33 pp, per `docs/preregistration.md`);
      - the skeptic (live month: search + extract; ≥ 2 verified contrary quotes → widen by 50%);
      - coverage, top 3 contributors (pp), with/without-Tavily attribution, `evidence_cutoff_utc`, manifest path,
        code commit, model IDs.

      ⚠️ The builder script for this file is **not written yet** (the replay used `tools/score_replay.py`). It
      must call the same `predict_month(..., "c", ...)`, so the code that was scored is the code that is sealed.
- [ ] Commit everything (the real seal refuses with uncommitted changes).

## 3. Seal (29 Oct)
- [ ] `python seal_month.py 2026-10 --dry-run`: every line must be PASS. Then delete `sealed/dry-run/`.
- [ ] `python seal_month.py 2026-10`: writes `sealed/2026-10.json` + `.sha256`, commits, tags `seal-2026-10`,
      pushes the branch and the tag.
- [ ] Check it from outside, following `verify.md` (download at the tag, recompute the SHA-256).
- [ ] Put the SHA-256 into `docs/devpost_draft.md` (`[TBD: from seal]`).
- [ ] Tag `submission-v1.0` before submitting (Prompt 5). After it, prompts, weights, item list, source rules and
      scoring must not change.

## 4. After the release (12 Nov)
- [ ] Add the official October figure to `data/official_releases.csv` (`month,official_yoy,release_date,source_url`).
- [ ] `python score.py`: writes `results/archive.csv` with the miss, whether it was inside the range, and the main
      surprise.

## Never
- Never change the prediction, the range or the rules after the seal. A seal is never redone.
- Never solve or bypass a CAPTCHA in software.
- Never put a key in a committed file.
