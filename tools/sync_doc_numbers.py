#!/usr/bin/env python3
"""Fill the run-dependent Tavily counts in README.md and docs/devpost_draft.md from the results files.

    python tools/sync_doc_numbers.py                 # as of today (0 credits)
    python tools/sync_doc_numbers.py --as-of 2026-10-25
    python tools/sync_doc_numbers.py --check         # exit 1 if a doc would change; writes nothing

Run-dependent counts (calls sent, credits used, results inside the date window, median latency) grow with every
run, so they are not edited after each task: this runs once in the Sunday consistency pass and again after the
seal. It rewrites only the passages below, each labelled "as of <date>"; scored numbers from
results/score_lock.json and every other line are left as they are. Counts come from tools/prompt_t.py run_stats
(flight recorder, credit ledger, config/budget.json, cached Tavily responses), the same code as the report card.
"""
import re
import sys
import textwrap
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from prompt_t import run_stats  # noqa: E402


def human(d):
    return f"{d.day} {d:%b} {d.year}"


def readme_passage(st, as_of):
    text = (f"Measured in [`results/tavily_report_card.md`](results/tavily_report_card.md) (as of {human(as_of)}): "
            f"{st['calls']:,} Tavily calls sent, {st['credits']:,} credits used (of a {st['plan_limit']:,}-credit "
            f"monthly plan plus {st['addon_credits']:,} add-on credits), {st['inside'] / st['total']:.0%} of dated "
            f"search results inside the requested window.")
    return textwrap.fill(text, width=120, break_on_hyphens=False, break_long_words=False)


def devpost_lines(st, as_of):
    tag = f"as of {human(as_of)}"
    return {
        "calls": f"  - calls: {st['calls']:,} Tavily calls sent (cached repeats and free balance checks not counted); "
                 f"{st['credits']:,} credits used, of a {st['plan_limit']:,}-credit monthly plan plus "
                 f"{st['addon_credits']:,} add-on credits from the Nebius builder program ({tag})",
        "window": f"  - share of dated search results inside the requested window: {st['inside'] / st['total']:.0%} "
                  f"({st['inside']:,} of {st['total']:,}; {tag})",
        "latency": f"  - median latency: {st['median_latency_s']:.1f} s per Tavily call ({tag})",
    }


# (file, pattern matching exactly one passage, replacement key); patterns anchor on the wording, not the numbers
TARGETS = [
    ("README.md", re.compile(r"^Measured in \[`results/tavily_report_card\.md`\].*?requested\s+window\.$", re.M | re.S),
     "readme"),
    ("docs/devpost_draft.md", re.compile(r"^  - calls: .*Tavily calls sent.*$", re.M), "calls"),
    ("docs/devpost_draft.md", re.compile(r"^  - share of dated search results inside the requested window: .*$", re.M),
     "window"),
    ("docs/devpost_draft.md", re.compile(r"^  - median latency: .* per Tavily call.*$", re.M), "latency"),
]


def sync(st, as_of, root=ROOT, write=True):
    """Rewrite the passages; returns the files that changed. Raises if a passage is missing or not unique."""
    new = {"readme": readme_passage(st, as_of), **devpost_lines(st, as_of)}
    texts, changed = {}, []
    for rel, pat, key in TARGETS:
        s = texts.setdefault(rel, (root / rel).read_text(encoding="utf-8"))
        hits = pat.findall(s)
        if len(hits) != 1:
            raise SystemExit(f"{rel}: expected one '{key}' passage, found {len(hits)}; fix the doc or the pattern")
        texts[rel] = pat.sub(lambda _: new[key], s)
    for rel, s in texts.items():
        if s != (root / rel).read_text(encoding="utf-8"):
            changed.append(rel)
            if write:
                (root / rel).write_text(s, encoding="utf-8")
    return changed


def main(argv):
    as_of = date.fromisoformat(argv[argv.index("--as-of") + 1]) if "--as-of" in argv else date.today()
    st = run_stats()
    if not st["total"] or st["median_latency_s"] is None:
        raise SystemExit("no uncached Tavily calls in the flight recorder; nothing to sync")
    changed = sync(st, as_of, write="--check" not in argv)
    print(f"as of {as_of}: {st['calls']} calls, {st['credits']} credits, {st['inside']} of {st['total']} inside the "
          f"window, median {st['median_latency_s']:.1f} s; " + (f"changed: {', '.join(changed)}" if changed
                                                                  else "docs already match"))
    if "--check" in argv and changed:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
