# Judging operations (judging period 9 Dec 09:00 PT to 23 Dec 12:00 PT, 2026)

What has to be true for the app to stay free, live and honest while judges use it, and what a judge sees when it is
not. Written 29 Oct 2026; dates corrected 31 Oct 2026 from the official rules (nebiusglobalaihackathon.devpost.com/rules):
the Judging Period runs from 9 Dec 2026 9:00 PT to 23 Dec 2026 12:00 PT (24 Dec 01:30 IST), winners are announced around
25 Jan 2027, and the project must stay available and working until judging ends. The app's own line "Live runs open on
1 Dec" is unchanged: live runs open before judging starts. Nothing here changes a cap: the caps live in `config/budget.json`, and
`tests/test_judging_failures.py` fails if the table below drifts from it.

## 1. Tavily credits against the caps

| Setting in `config/budget.json` | Value | What it limits |
|---|---|---|
| `plan_limit` | 1000 | Monthly plan, as Tavily's GET /usage reports it (the billing page showed 1,500; we use the lower figure) |
| `addon_credits` | 3125 | Nebius builder-program add-on credits; /usage does not count them, the ledger does |
| `reserve` | 150 | Kept back for `reserve_for` only: `live-month`, `nov-interim-scan`, `skeptic` |
| `caps.live-month` | 120 | The November seal's full live run (about 120 credits) |
| `caps.nov-interim-scan` | 30 | The two interim November scans |
| `caps.run-now` | 120 | Every "Run live" press on Home, all days together |
| `plans.try-it.per_run` | 2 | One Try-it run is two basic searches |
| `plans.try-it.per_day` | 25 | Try-it, whole app, per UTC day |
| `plans.try-it.lifetime` | 600 | Try-it, whole app, in all |
| `plans.app_live.credit_floor` | 400 | Ledger balance Run live and Try-it will not go below |
| `plans.app_live.usage_floor` | 400 | Same, from Tavily's own /usage (fails closed) |

Where the ledger stands (`results/credit_ledger.jsonl`, 2,229 rows, read 31 Oct 2026, 0 credits to read it):
2,178 credits spent of 4,125 (plan 1,000 plus add-on 3,125), so 1,947 left on our books. Try-it has used 2 of its 600;
the November seal cap (120) has used 3; the skeptic cap (48) has used 30; Run live has used none of its 120.

Worst case from now to 23 Dec 12:00 PT (24 Dec 01:30 IST) if every cap is used in full: Try-it 598 + November seal 117 +
interim scans 30 + skeptic 18 + Run live 120 = 883 credits, which is under the 1,947 left on the ledger (1,064 to
spare). The caps are lifetime caps, so the longer window adds nothing to this total; inside the 15 days of judging itself
Try-it can spend at most 25 a day, 375 in all. The binding limit is not the
ledger but the floors: below 400 credits left (plan from /usage plus add-on left on the ledger) Run live and Try-it
pause themselves and show the saved example. The floors are enforced in `live_run.gate` and `try_it.run`; the seal
scripts are held by their own caps and the 150 reserve in `shadow_cpi/budget.py`.

To re-check before each step (read-only, 0 credits; Tavily's own balance is on its dashboard and is the figure to trust,
because /usage can lag and the ledger is our estimate):

```bash
python3 -c "from shadow_cpi import budget as B; c=B.load_budget(); l=B.read_ledger(); print('left on ledger', B.account_limit(c)-B.account_spent(c,l)); print({n: (B.spent(n,l), c['caps'][n]) for n in ('try-it','live-month','run-now','nov-interim-scan','skeptic')})"
```

## 2. Nebius (Nemotron) balance

The repo records no Nebius balance and no per-token price, so **I cannot state the balance needed**; do not read a figure
into this section. What the code does tell us:

- Only two paths call Nemotron live: Run live on Home (`shadow_cpi/live_run.py`, up to 120 scans in all because
  `caps.run-now` is 120 credits and a scan costs at least 1 credit; the app allows 8 per UTC day and 3 per visit) and the
  November seal on 10 Dec. Try it and the Leak demo's live search call Tavily only; the Field Report makes no call.
- Each Run live shows a receipt with its Nemotron call count ("Nemotron calls N"); multiply by the Token Factory price
  for the model named in the receipt to get the cost per press. Do this once after the first live press and size the
  balance as: November seal + (presses expected, at most 8 a day) through 23 Dec 12:00 PT.
- **Gap:** the app checks Tavily's balance before a live run (`live_run.gate`) but not Nebius's. If Nebius runs out the run
  fails after it starts (section 3); nothing breaks, but a judge presses a button and gets the saved run.
- From 9 Nov 2026 the original Nemotron models are retired and calls use the replacements
  (`docs/honest_limits.md`); the receipt names the models used.

Owner to do: read the Token Factory balance in the Nebius console on 29 Oct and again after the first live press, and
keep it above the size computed from the receipt through 23 Dec 12:00 PT. Nebius is the part this document cannot
size: the repo records no Nebius balance or price, so whether the Nebius balance covers the longer window is not known.

## 3. What the app shows when something fails

A cap, a missing or rejected key, an exhausted Tavily or Nebius balance, a retired model, a timeout or a network error
all end the same way: a plain sentence and the saved result. Never an error box, never a stack trace, never the key.

| Page | What fails | What the judge sees |
|---|---|---|
| Home, "Run live" | No `RUN_LIVE_ENABLED`, no keys, per-visit or per-day cap, balance under a floor, `/usage` unreadable | The gate's sentence ("Live runs are paused: ...") and the saved run (`results/app/saved_run.json`) |
| Home, "Run live" | Anything raised after the run starts: Tavily 432/433/401, Nebius key or retired model, timeout, network | "The live run could not finish (TimeoutError). Showing the saved run." and the saved run |
| Try it | Cap reached, no key, balance under a floor, `/usage` unreadable | The sentence, a link to the Colab notebook, and the saved example (Leak demo case F3) |
| Try it | Any exception during the two searches | "The search could not finish (ApiError). Please try again later." and the saved example |
| Try it | The visitor's own mistake (empty question, cutoff out of range) | A plain warning only; there is nothing to show instead |
| Leak demo, "Try it live" | Off, gated, or an exception | A sentence; the page above it is already saved results |

Tested with fake failing clients (no network, no credits): `tests/test_judging_failures.py` runs the real `run_live`
with Tavily and Nebius transports that raise each of 432, 433, 401, a retired-model 404, a timeout and a network error,
and the real Try it run with a failing client, and checks the page has no exception, no error element, no key and the
saved result on screen.
