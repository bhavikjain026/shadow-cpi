# October 2026 radar: pre-registration

**Written 2026-10-22T09:38:55Z (UTC), committed before any radar run.** Decided by the owner. Code: `v2/radar.py`; page:
`app_pages/radar.py`; tests: `tests/test_v2_radar.py`. A **report-only** prospective test: it never changes v1,
the v2 score locks or the October seal.

**What.** Announced retail price changes in India taking effect in **October 2026**, found before MoSPI publishes
October CPI, frozen, then scored against a list built independently afterwards.

1. **Window and freeze.** Evidence window = `v2.rules.window("2026-10")` (21 Sep to 29 Oct). The radar is
   **frozen at 29 Oct 2026, 23:59 IST (18:29 UTC)**: `python -m v2.radar --freeze` writes
   `v2/radar/radar_2026-10.frozen.json` and its SHA-256 and is committed; no run is accepted after that time, and
   nothing is added after the freeze.
2. **Search plan.** The winning strategy of the four-arm table (A fixed, B model-written, C model-written + regional,
   T Tavily auto) under Amendment F's rule (rank 1 of `results/v2_ablation.json` `equivalence.ranking`). It is
   written into this file as a timestamped line **"Search strategy decided: X"** before the first radar run; the code
   refuses to run without it. **Discovery** searches use `include_domains_mode` **prefer**. **Corroboration:** for
   each verified event, where a primary source's domain is known (`v2/radar_primary.json`: regulators, utilities,
   oil companies, dairies, railways, government sites), one search **restricted** (`include_domains_mode`
   restrict) to that domain, same window. **Optional:** at most one Tavily Research call per day with an
   `output_schema` of candidate events, **proposals only** (every hit must pass the verifier); not implemented in
   this commit and off unless added by a later dated line here.
3. **Verification rule.** The v2 verifier, unchanged (Amendments A–D: cited line, number in the line, effective date
   in October, page published in the window, page-date check, retail price type). Two tiers:
   - **verified:** passes the verifier;
   - **corroborated:** verified **and** either **2 independent, non-syndicated publishers** (different registrable
     domains, and their cited lines are not the same text after normalising) or **1 primary source** (a page on a
     `.gov.in` / `.nic.in` domain or a domain in `v2/radar_primary.json`).
   An **event** is a distinct (kind, effective date, set of states), as in Amendment E.
4. **"Tavily-only."** An event of a kind with **no government spine series and no official observed series**
   (Amendment A role "moves": electricity, diesel, bus, rail, mobile) whose verified sources were all found with
   Tavily Search and read with Tavily Extract. These are the changes the October nowcast could know only through
   Tavily.
5. **Effect formula.** Each event's effect on October headline CPI inflation, in percentage points:
   effect = needle(item trend + change × share of October in force × state share) − needle(everything on trend),
   with `v2.needle.yoy` (v1's frozen maths: 2024 weights, index levels, year-on-year last). Share of October in
   force = days from the effective date to 31 Oct ÷ 31; state share = Amendment A rule 2 (`v2.rules.geography`).
   Reported per event and summed for Tavily-only events. Report only: it does not change the sealed call.
6. **Matching rule.** The Amendment C matcher (`v2/recall.py` `matches`, db2984c, unchanged): same kind (fuel =
   petrol or diesel), effective date within ±2 days where the list gives a day, shared state for a state change.
7. **Scoring list and scores.** Built **after the freeze, independently of Tavily** (by hand and with other search
   tools), in `v2/radar/scoring_list_2026-10.json`, each change with the date it was **first reported**. Changes
   first reported after 29 Oct 23:59 IST are **not misses** (left out of recall). For each tier: **precision** =
   radar events that match a listed change ÷ radar events; **recall** = listed changes (first reported by the freeze)
   matched by a radar event ÷ those changes. Scored once (`python -m v2.radar --score`); the score file refuses a
   second run.
8. **Credits.** Cap `radar-2026-10` in `config/budget.json`: **150** proposed; the owner may change it by a dated
   line here before the first run. A cap stops a run cleanly and marks it incomplete.

**Search strategy decided: A (fixed templates), per Amendment F, results 5b1eec0.** Written 2026-10-22T12:11:28Z (UTC), 2026-10-22, before any radar run.

**Domain list fixed, 2026-10-25T13:04:16Z (UTC), before any radar run.** Every primary-source domain was opened directly on
2026-10-25 (no Tavily credits; `v2/RADAR_DOMAIN_CHECK.md`). Replaced in `v2/radar_primary.json`: electricity /
Tamil Nadu tnerc.gov.in → tnerc.tn.gov.in; electricity / Jammu and Kashmir jkserc.nic.in → jpdcl.jk.gov.in; bus /
Karnataka ksrtc.in → ksrtc.karnataka.gov.in. Nothing else in this file changes; strategy A and the 150 cap stand.
