#!/usr/bin/env python3
"""Prompt 5.4 - score sealed nowcasts once MoSPI has released the official number.

Run:  python score.py

1. After a release, add one line to data/official_releases.csv:
       month,official_yoy,release_date,source_url
       2026-10,5.12,2026-11-12,https://www.mospi.gov.in/...
2. Run this script. For every sealed month (sealed/<month>.json) it writes one row to results/archive.csv:
   the sealed number and range, the official number, the miss (nowcast minus official, in percentage points),
   whether the official number fell inside the range, whether the seal still matches its SHA-256, and the
   main surprise: the division whose real contribution differed most from the sealed contribution.
   From October 2026 on (docs/after_scoring_changes.md, a new metric): the Brier score of the sealed
   P(headline >= 6.0%), (p - outcome)^2 with outcome 1 if the official number is >= 6.0, else 0. Not applied to
   earlier months (they sealed no probability).
   Months without an official number yet are listed as "waiting for release".
The sealed files are only read, never changed. No API calls. Plain code, no AI.
"""
import csv
import json
import sys
from pathlib import Path

from shadow_cpi import cpi_math as M
from shadow_cpi import official as O
from shadow_cpi import seal as S
from shadow_cpi.live_range import THRESHOLD

ROOT = Path(__file__).resolve().parent
RELEASE_FIELDS = ["month", "official_yoy", "release_date", "source_url"]
ARCHIVE_FIELDS = ["month", "sealed_yoy", "range_low", "range_high", "official_yoy", "release_date", "source_url",
                  "miss_pp", "inside_range", "main_surprise", "main_surprise_pp", "p_headline_ge_6", "brier_ge_6",
                  "seal_check", "sha256"]
BRIER_FROM = "2026-10"          # new metric from October on; earlier months are not re-scored with it


def brier(month, sealed, official):
    """(p, Brier score) for P(headline >= 6.0%) from October on; ('', '') before October or without a sealed p."""
    p = sealed.get("p_headline_ge_6")
    if month < BRIER_FROM or p is None:
        return "", ""
    return p, (p - (1.0 if official >= THRESHOLD else 0.0)) ** 2


def read_releases(path):
    if not Path(path).exists():
        return {}
    with Path(path).open(encoding="utf-8", newline="") as f:
        return {r["month"]: r for r in csv.DictReader(f) if (r.get("official_yoy") or "").strip()}


def sealed_contributions(sealed):
    """{division code: pp} from the seal: a full 'contributions' dict if present, else the 'contributors' list."""
    if isinstance(sealed.get("contributions"), dict):
        return {str(k): float(v) for k, v in sealed["contributions"].items()}
    return {str(c["code"]): float(c["pp"]) for c in sealed.get("contributors", []) if "code" in c and "pp" in c}


def actual_contributions(month, tidy):
    """{division code: pp} from official division index LEVELS and 2024-series weights, or None if missing."""
    series, weights, _, meta = tidy
    divs = [c for c, m in meta.items() if m["level"] == "division" and c in weights]
    prev = M.add_months(month, -12)
    now = {c: series[c][month] for c in divs if month in series[c]}
    old = {c: series[c][prev] for c in divs if prev in series[c]}
    if not now or set(now) != set(old):
        return None
    return M.contributions_yoy(now, old, {c: weights[c] for c in divs})


def main_surprise(sealed, month, tidy):
    """(text, pp gap) for the division with the largest |actual - sealed| contribution."""
    pred = sealed_contributions(sealed)
    if not pred:
        return "not available (the seal has no contributions)", ""
    if tidy is None:
        return "not available (data/cpi_tidy.csv not found)", ""
    actual = actual_contributions(month, tidy)
    if actual is None:
        return f"not available yet (add {month} division indices to data/cpi_tidy.csv: python build_official.py)", ""
    common = [c for c in pred if c in actual]
    if not common:
        return "not available (seal and official data share no divisions)", ""
    code = max(common, key=lambda c: abs(actual[c] - pred[c]))
    gap = actual[code] - pred[code]
    name = tidy[3][code]["name"]
    word = "added more than" if gap > 0 else "added less than"
    return f"{name} {word} sealed ({pred[code]:+.2f} pp sealed vs {actual[code]:+.2f} pp actual)", gap


def score(root=ROOT, out=print):
    root = Path(root)
    seal_dir = root / "sealed"
    releases = read_releases(root / "data" / "official_releases.csv")
    tidy_path = root / "data" / "cpi_tidy.csv"
    tidy = O.load_tidy(tidy_path) if tidy_path.exists() else None
    rows = []
    for jp in sorted(seal_dir.glob("*.json")):
        month = jp.stem
        sealed = json.loads(jp.read_text(encoding="utf-8"))
        ok = (seal_dir / f"{month}.sha256").exists() and S.verify(month, seal_dir=seal_dir)
        sha = (seal_dir / f"{month}.sha256").read_text(encoding="utf-8").strip() if ok else ""
        row = {"month": month, "sealed_yoy": sealed["headline_yoy"], "range_low": sealed["range_low"],
               "range_high": sealed["range_high"], "seal_check": "PASS" if ok else "FAIL", "sha256": sha}
        rel = releases.get(month)
        if rel:
            off = float(rel["official_yoy"])
            miss = sealed["headline_yoy"] - off
            inside = sealed["range_low"] <= off <= sealed["range_high"]
            surprise, gap = main_surprise(sealed, month, tidy)
            p, bs = brier(month, sealed, off)
            row.update(official_yoy=off, release_date=rel.get("release_date", ""), source_url=rel.get("source_url", ""),
                       miss_pp=miss, inside_range="yes" if inside else "no", main_surprise=surprise,
                       main_surprise_pp=gap, p_headline_ge_6=p, brier_ge_6=bs)
            out(f"[{row['seal_check']}] {month}: sealed {sealed['headline_yoy']:.2f}%, official {off:.2f}%, "
                f"miss {miss:+.2f} pp, inside range: {row['inside_range']}. Main surprise: {surprise}"
                + ("" if bs == "" else f". P(>= 6.0%) sealed {p:.2f}, Brier {bs:.3f}"))
        else:
            row.update(main_surprise="waiting for release")
            out(f"[{row['seal_check']}] {month}: sealed {sealed['headline_yoy']:.2f}% - waiting for the official release")
        rows.append(row)
    out_path = root / "results" / "archive.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ARCHIVE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    out(f"Wrote results/archive.csv ({len(rows)} sealed month{'s' if len(rows) != 1 else ''}).")
    return rows


if __name__ == "__main__":
    rows = score()
    sys.exit(1 if any(r["seal_check"] == "FAIL" for r in rows) else 0)
