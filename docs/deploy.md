# Deploying the app to Streamlit Community Cloud (by hand)

Nothing here has been run. These are the steps to do yourself. Streamlit Community Cloud deploys straight from the
GitHub repository (`bhavikjain026/shadow-cpi`, branch `main`) and redeploys on every push to `main`. Nothing goes to
Hugging Face.

## What the app needs

| Item | Where it comes from |
|---|---|
| Entry point | `app.py` (pages in `app_pages/`) |
| Packages | `requirements.txt`: streamlit 1.66.0, pandas 3.0.6, altair 6.3.0 (the versions the tests ran with) |
| Python | 3.12, chosen in *Advanced settings* when you deploy (pandas 3 needs 3.11 or newer) |
| Data | the committed files in `results/`, `results/app/`, `manifests/`, `data/`, `config/`, `audit/`, `docs/` |
| Keys (only for "Run live") | Streamlit **secrets** `SCPI_TAVILY_API_KEY`, `SCPI_NEBIUS_API_KEY`. Streamlit Cloud exposes root-level secrets as environment variables; the app reads the environment first and Streamlit's secrets as a read-only fallback (`shadow_cpi/live_run.py`, `setting()`). Without keys the app still works. |
| Live-run switch | secret `RUN_LIVE_ENABLED`, **not set until 30 Nov**. While it is missing, "Run live" shows "Live runs open on 1 Dec (judging period)" and makes no call. |

`cache/` and `logs/` are not committed. The app reads the committed snapshots in `results/app/`, so refresh them
before each push that should change what the app shows (step 1).

## Steps

1. **Refresh the app's data and push `main`** (0 credits):
   ```bash
   .venv/bin/python tools/build_app_data.py
   ```
   ```bash
   .venv/bin/python -m pytest -q
   ```
   Commit and push `main`.

2. **Create the app.** Go to share.streamlit.io and sign in with GitHub → **Create app** → *Deploy a public app
   from GitHub*:
   - Repository `bhavikjain026/shadow-cpi`, branch `main`, main file path `app.py`.
   - App URL: pick a subdomain, e.g. `shadow-cpi` → `https://shadow-cpi.streamlit.app`.
   - **Advanced settings** → Python version **3.12** → Secrets (TOML), exactly two lines:
     ```toml
     SCPI_TAVILY_API_KEY = "your Tavily key"
     SCPI_NEBIUS_API_KEY = "your Nebius Token Factory key"
     ```
     Do **not** add `RUN_LIVE_ENABLED` yet.
   - **Deploy.** Secrets stay in Streamlit's dashboard; never put them in a file in the repository
     (`.streamlit/secrets.toml` is git-ignored).

3. **Check the app** once it has built:
   - Home shows "sealing on 29 Oct", the countdown to Thu 12 Nov 4:00 PM IST, the scoreboard, the audit box and
     the saved run.
   - Press "Run live": it shows the saved run with "Live runs open on 1 Dec (judging period)" and spends nothing.
   - No page shows an error box. In the app's settings → *Sharing*, the app is public.

4. **Turn on the keep-awake job.** GitHub → the repository → Settings → *Secrets and variables* → *Actions* →
   **Variables** → New repository variable `APP_URL` = the app's address (e.g. `https://shadow-cpi.streamlit.app`).
   Then Actions → **keep-awake** → *Run workflow* once and check that it ends green. It runs every 6 hours after that.
   It uses no secrets, makes no API call, and only clicks Streamlit's "get this app back up" button when the app
   is asleep. It never presses "Run live".

5. **29 Oct, after the seal:** repeat step 1 (`tools/build_app_data.py`, tests, push `main`). Streamlit Cloud
   redeploys on the push, and Home then shows the sealed number, its range, P(headline ≥ 6.0%) and the
   fingerprint from `sealed/2026-10.json`.

6. **30 Nov, turn live runs on.** share.streamlit.io → the app → ⋮ → **Settings** → **Secrets** → add a third line
   and **Save**:
   ```toml
   RUN_LIVE_ENABLED = "1"
   ```
   The app restarts; no code changes. Press "Run live" once (up to 8 credits): a receipt appears. To turn it off,
   delete that line (or set it to `"0"`) and save.

## Things to know

- **Sleeping apps.** Community Cloud puts an app to sleep after a stretch without visitors; a visitor then sees a
  "get this app back up" button and waits for it to start. The keep-awake job (step 4) presses it every 6 hours.
  GitHub turns scheduled workflows off after 60 days without activity in the repository, which is after judging
  ends (23 Dec 12:00 PT = 24 Dec 01:30 IST; judging runs 9 Dec 09:00 PT to 23 Dec 12:00 PT, winners around 25 Jan 2027). Open the app yourself before a demo.
- **Live-run guards.** Before every live run the app asks Tavily for the real balance (GET /usage, same key) and
  refuses the run if fewer than 400 credits are left, or if that check fails or returns no limit. It also keeps the
  ledger check (100-credit floor), at most 8 runs per day for the whole app and 3 per visitor, and the per-run caps
  (8 credits per scan, 120 for all scans). The per-day count and the ledger live inside the running app and reset
  on a reboot or redeploy; the /usage check does not, so it is the one that holds the balance. /usage can lag: on
  20 Oct it showed 6 credits used against 226 spent; on 21 Oct it showed 596 against the ledger's 694 (which
  includes a 160-credit estimate for calls made before the ledger existed). The 150 floor leaves room for that.
- **/usage does not count add-on credits; the plan limit is set to 1,000 (checked 22 Oct).** The account has a
  monthly plan plus 3,125 add-on credits from the Nebius builder program, with pay-as-you-go off. The billing page
  showed a 1,500-credit plan, but GET /usage reports `account.plan_limit` 1000 (`plan_usage` 697, `paygo_limit` null,
  `paygo_usage` 0, no add-on field). `config/budget.json` uses the lower figure, 1,000, until the two agree. Before
  every live run the app computes **remaining = (plan_limit − plan_usage, from GET /usage) + (add-on credits in
  `config/budget.json` − add-on credits used, from the ledger)** and refuses the run below 400. If /usage fails or
  returns no limit, the run is refused.
- **Assumption: Tavily spends plan credits before add-on credits.** So add-on credits count as used only for
  spending beyond the plan limit that /usage reports (ledger total, reconciled to the billing page, minus that limit).
  The ledger is cumulative: after the monthly plan reset, add-on credits already counted as used stay counted. That
  errs towards refusing a run, never towards overspending. If Tavily's billing page ever shows add-on credits being spent while plan credits remain, this
  assumption is wrong: lower `addon_credits` in `config/budget.json` to what the billing page shows.
- **Untested on Python 3.12 at run time.** The code was tested on Python 3.14 here; a 3.12 grammar check of every
  file passed. If the build fails, delete the app and redeploy with Python 3.13 (the version is set at deploy time).
