#!/usr/bin/env python3
"""Score the sealed October 2026 nowcast once MoSPI has published the October headline CPI (due 12 Nov 2026).

    python tools/score_october.py 5.92                          # the official year-on-year figure, in percent
    python tools/score_october.py 5.92 --release-date 2026-11-12 --source-url https://www.mospi.gov.in/...
    python tools/score_october.py 5.92 --dry-run                # print the scoring, write nothing

What it does (plain code, no AI, no API call; the sealed files are only read):
  1. Checks the sealed file still matches its SHA-256 (refuses to score a seal that fails).
  2. Appends one line to data/official_releases.csv (refuses to overwrite a month already recorded, unless --replace).
  3. Runs score.score(): the miss (sealed minus official, in percentage points), whether the official figure fell inside
     the sealed 80% range, the largest division surprise, and the Brier score of the sealed P(headline >= 6.0%):
     (p - outcome)^2, outcome 1 if the official figure is >= 6.0 else 0. Writes results/archive.csv.
  4. The Archive page (app_pages/archive.py) reads data/official_releases.csv and results/archive.csv, so it shows the
     scoring as soon as both are committed.
--root DIR scores a copy of the repository layout (sealed/, data/, results/) instead of this one; the tests use it with
a made-up value, so nothing real is ever written by a test.
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import score as SC  # noqa: E402
from shadow_cpi import seal as S  # noqa: E402

MONTH = "2026-10"
DEFAULT_RELEASE = "2026-11-12"          # MoSPI's scheduled date (app_pages/common.py RELEASES)


def record(root, month, official, release_date, source_url, replace=False):
    """Add (or with replace=True, overwrite) the month's line in data/official_releases.csv."""
    path = Path(root) / "data" / "official_releases.csv"
    rows = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    if any(r["month"] == month and (r.get("official_yoy") or "").strip() for r in rows) and not replace:
        raise SystemExit(f"{month} is already recorded in data/official_releases.csv; use --replace to change it")
    rows = [r for r in rows if r["month"] != month]
    rows.append({"month": month, "official_yoy": f"{official}", "release_date": release_date, "source_url": source_url})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SC.RELEASE_FIELDS)
        w.writeheader()
        w.writerows(rows)


def summary(row):
    """The scoring in plain words, from one results/archive.csv row."""
    inside = "inside" if row["inside_range"] == "yes" else "outside"
    lines = [f"Sealed {float(row['sealed_yoy']):.2f}% (80% range {float(row['range_low']):.2f}% to "
             f"{float(row['range_high']):.2f}%); official {float(row['official_yoy']):.2f}%.",
             f"Miss (sealed minus official): {float(row['miss_pp']):+.2f} percentage points; the official figure is "
             f"{inside} the range."]
    if row["brier_ge_6"] != "":
        p, bs = float(row["p_headline_ge_6"]), float(row["brier_ge_6"])
        hit = float(row["official_yoy"]) >= SC.THRESHOLD
        lines.append(f"P(headline >= {SC.THRESHOLD:.1f}%) was sealed at {p:.2f}; the official figure is "
                     f"{'at or above' if hit else 'below'} {SC.THRESHOLD:.1f}%, so the Brier score is {bs:.3f} "
                     "(0 is perfect; always saying 50% scores 0.250).")
    lines.append(f"Main surprise: {row['main_surprise']}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("official_yoy", type=float, help="MoSPI's October year-on-year CPI inflation, in percent")
    ap.add_argument("--release-date", default=DEFAULT_RELEASE)
    ap.add_argument("--source-url", default="https://www.mospi.gov.in/")
    ap.add_argument("--month", default=MONTH)
    ap.add_argument("--root", default=str(ROOT), help="repository layout to score (default: this repository)")
    ap.add_argument("--replace", action="store_true", help="overwrite a month already recorded")
    ap.add_argument("--dry-run", action="store_true", help="print the scoring; write nothing")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not 0 < a.official_yoy < 25:
        raise SystemExit(f"{a.official_yoy} is not a plausible year-on-year CPI figure in percent")
    date.fromisoformat(a.release_date)
    if not (root / "sealed" / f"{a.month}.json").exists() or not S.verify(a.month, seal_dir=root / "sealed"):
        raise SystemExit(f"sealed/{a.month}.json is missing or does not match its SHA-256: not scoring")
    if a.dry_run:
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:           # score a scratch copy, leave the repository alone
            for d in ("sealed", "data"):
                if (root / d).exists():
                    shutil.copytree(root / d, Path(tmp) / d)
            record(tmp, a.month, a.official_yoy, a.release_date, a.source_url, replace=True)
            rows = SC.score(root=tmp, out=lambda *_: None)
    else:
        record(root, a.month, a.official_yoy, a.release_date, a.source_url, replace=a.replace)
        rows = SC.score(root=root)
    row = next(r for r in rows if r["month"] == a.month)
    print("\n".join(summary(row)))
    if a.dry_run:
        print("(dry run: nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
