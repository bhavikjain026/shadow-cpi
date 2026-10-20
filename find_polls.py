#!/usr/bin/env python3
"""Find the economists' poll median for each test month (Jan-Sep 2026) with Tavily -> data/poll.csv.

    python find_polls.py          # prints the credit estimate and stops
    python find_polls.py --go     # spends the credits (cached: re-running is free)
"""
import sys

from shadow_cpi import polls
from shadow_cpi.official import TEST_MONTHS
from shadow_cpi.recorder import Recorder, credits_used, read_log
from shadow_cpi.tavily import Tavily


def main():
    est = polls.estimate_credits(TEST_MONTHS)
    print(f"Tavily credit estimate: at most {est} (about {est // 2} if the first query finds each poll)")
    if "--go" not in sys.argv:
        print("Run again with --go to spend them.")
        return
    rec = Recorder()
    before = len(read_log())
    tav = Tavily(recorder=rec)
    rows = []
    for m in TEST_MONTHS:
        row, notes = polls.find_month(tav, m)
        rows.append(row)
        print(f"{m}: median={row['median_forecast']} n={row['n_economists']} date={row['published_at']} "
              f"url={row['source_url']}")
        if row["evidence_line"]:
            print(f"    line: {row['evidence_line'][:300]}")
        for n in notes[-3:]:
            print(f"    note: {n}")
    polls.write_poll(rows)
    print(f"Wrote data/poll.csv. Tavily credits used now: {credits_used(read_log()[before:])}")


if __name__ == "__main__":
    main()
