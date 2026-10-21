# Deploying the app to Hugging Face Spaces (by hand)

Nothing here has been run. These are the steps to do yourself. The app is a Streamlit Space; `README.md` starts
with the Spaces header block (SDK `streamlit` 1.66.0, Python 3.12, entry point `app.py`).

## What the Space needs

| Item | Where it comes from |
|---|---|
| Entry point | `app.py` (pages in `app_pages/`) |
| Packages | `requirements.txt` (pandas, altair; Streamlit comes from `sdk_version`) |
| Data | the committed files in `results/`, `results/app/`, `manifests/`, `data/`, `config/`, `audit/`, `docs/` |
| Keys (only for the "Run live" button) | Space **secrets** `SCPI_TAVILY_API_KEY` and `SCPI_NEBIUS_API_KEY`. The app reads them from the environment only, never from a file. Without them the app still works and "Run live" says live runs are switched off. |

`cache/` and `logs/` are not committed. The app reads the committed snapshots in `results/app/` instead, so refresh
them before each push (step 1).

## Steps

1. **Refresh the app's data and commit it** (0 credits):
   ```bash
   .venv/bin/python tools/build_app_data.py
   ```
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Commit and push `main` as usual.

2. **Create the Space.** On huggingface.co: New Space → name `shadow-cpi` → SDK **Streamlit** → hardware
   **CPU basic (free)** → **Public**. Leave it empty.

3. **Add the two secrets.** Space → Settings → *Variables and secrets* → **New secret** (not "New variable"):
   - `SCPI_TAVILY_API_KEY` = your Tavily key
   - `SCPI_NEBIUS_API_KEY` = your Nebius Token Factory key

4. **Push a one-commit snapshot** (no history). Hugging Face refuses binary files (the PDF and the weights
   spreadsheet) unless they are stored with LFS, and the old commits contain them, so push a fresh branch:
   ```bash
   git checkout --orphan space-deploy
   ```
   ```bash
   git lfs install && git lfs track "*.pdf" "*.xlsx"
   ```
   ```bash
   git add -A && git status --short | grep -E "\.env$|^.. cache/|^.. logs/|^.. \.venv/" ; echo "nothing above = OK"
   ```
   ```bash
   git commit -m "Shadow CPI app snapshot"
   ```
   ```bash
   git remote add space https://huggingface.co/spaces/<your-hf-username>/shadow-cpi
   ```
   ```bash
   git push --force space space-deploy:main
   ```
   ```bash
   git checkout main && git branch -D space-deploy
   ```
   When git asks for a password, use a Hugging Face **write token** (Settings → Access Tokens), not your password.
   `.env` is git-ignored, so the `git add -A` line must print nothing before "OK".

5. **Check the Space** once the build log says "Running":
   - Home shows "sealing on 29 Oct", the countdown to Thu 12 Nov 4:00 PM IST, the scoreboard, the audit box and
     the saved run.
   - Press "Run live" once (up to 8 credits). A receipt appears (Tavily calls, credits, seconds). Optional cap
     check, up to 16 more credits: press it 3 more times; the fourth press shows the saved run with "You have used
     this visit's 3 live runs".
   - No page shows an error box.

6. **After the seal (29 Oct):** repeat steps 1 and 4 so the Space has `sealed/2026-10.json` and the new
   `results/nowcast_2026-10.json`.

## Things to know

- **Free Spaces sleep** after a period without visitors and take a short while to wake on the next visit. Judging
  runs to 15 Dec 12:00 PT (16 Dec 01:30 IST); visit the Space before a demo to wake it.
- **The live-run caps live inside the running Space** (`logs/live_runs.jsonl`, `results/credit_ledger.jsonl` in the
  container). A restart or rebuild resets the per-day count and forgets live credits spent since the last push. The
  hard caps still apply to each run (8 credits per scan, 120 for all scans), and the floor uses the committed ledger
  plus the container's runs. Check the Tavily dashboard during judging.
- **Untested on Python 3.12 at run time.** The code was tested on Python 3.14 here; a 3.12 grammar check of every
  file passed. If the build fails on 3.12, change `python_version` in the README header to `"3.13"`.
