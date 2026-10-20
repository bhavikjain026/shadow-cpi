"""seal_month.py (dry run only) and score.py, on a throwaway git repo with a fake prediction. No API calls."""
import csv
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import score as SC
import seal_month as SM
from shadow_cpi import official as O
from shadow_cpi import seal as S

ROOT = Path(__file__).resolve().parent.parent
MONTH = "2026-10"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def fake_prediction(**over):
    return {"target_month": MONTH, "headline_yoy": 5.31, "range_low": 4.86, "range_high": 5.82, "range_level": 0.8,
            "coverage": {"observed": 0.31, "carried": 0.69},
            "contributors": [{"code": "01", "name": "Food and beverages", "pp": 2.71}],
            "evidence_cutoff_utc": "2026-10-15T23:59:00+00:00", **over}


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    for f in ("data/cpi_tidy.csv", "config/models.json", "data/official_releases.csv"):
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / f, r / f)
    (r / SM.WEIGHTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    (r / SM.WEIGHTS_FILE).write_bytes(b"fake weights file")
    (r / "manifests").mkdir()
    (r / "manifests" / f"{MONTH}.json").write_text('{"month": "2026-10"}', encoding="utf-8")
    (r / "results").mkdir()
    (r / "results" / f"nowcast_{MONTH}.json").write_text(json.dumps(fake_prediction()), encoding="utf-8")
    git(r, "init", "-q")
    git(r, "config", "user.email", "test@example.com")
    git(r, "config", "user.name", "Test")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "fixture")
    return r


def dry(repo, **kw):
    lines = []
    digest = SM.run(MONTH, dry_run=True, root=repo, out=lines.append, **kw)
    return digest, "\n".join(lines)


# ---------- seal_month.py --dry-run ----------
def test_dry_run_writes_verifiable_seal_without_commit_tag_or_push(repo):
    head = git(repo, "rev-parse", "HEAD")
    digest, log = dry(repo)
    d = repo / "sealed" / "dry-run"
    assert S.verify(MONTH, seal_dir=d)
    assert (d / f"{MONTH}.sha256").read_text().strip() == digest
    assert "[DRY RUN]" in log and "[FAIL]" not in log
    assert git(repo, "rev-parse", "HEAD") == head          # no commit
    assert git(repo, "tag", "--list") == ""                # no tag
    assert not (repo / "sealed" / f"{MONTH}.json").exists()  # real seal slot left free


def test_sealed_file_holds_everything_prompt_5_asks_for(repo):
    dry(repo)
    p = json.loads((repo / "sealed" / "dry-run" / f"{MONTH}.json").read_text(encoding="utf-8"))
    assert p["headline_yoy"] == 5.31 and p["range_low"] == 4.86 and p["range_high"] == 5.82
    assert p["target_month"] == MONTH and p["git_tag"] == f"seal-{MONTH}"
    assert p["manifest"] == f"manifests/{MONTH}.json" and len(p["manifest_sha256"]) == 64
    assert p["code_commit"] == git(repo, "rev-parse", "HEAD")
    assert p["model_ids"] == json.loads((ROOT / "config" / "models.json").read_text())
    assert p["weights_file"] == SM.WEIGHTS_FILE
    assert p["weights_file_sha256"] == SM.sha256_file(repo / SM.WEIGHTS_FILE)
    assert p["evidence_cutoff_utc"] == "2026-10-15T23:59:00+00:00"
    assert p["sealed_at_utc"].endswith("+00:00")
    # canonical JSON written by shadow_cpi.seal
    text = (repo / "sealed" / "dry-run" / f"{MONTH}.json").read_text(encoding="utf-8")
    assert text == S.canonical(p)


def test_cutoff_flag_overrides_prediction(repo):
    dry(repo, cutoff="2026-10-14T12:00:00Z")
    p = json.loads((repo / "sealed" / "dry-run" / f"{MONTH}.json").read_text(encoding="utf-8"))
    assert p["evidence_cutoff_utc"] == "2026-10-14T12:00:00+00:00"


def test_dry_run_allows_uncommitted_changes_with_warning(repo):
    (repo / "config" / "models.json").write_text('{"small": "changed"}', encoding="utf-8")
    _, log = dry(repo)
    assert "[WARN] uncommitted changes" in log


def write_pred(repo, **over):
    (repo / "results" / f"nowcast_{MONTH}.json").write_text(json.dumps(fake_prediction(**over)), encoding="utf-8")


@pytest.mark.parametrize("change, reason", [
    (lambda r: write_pred(r, headline_yoy=None), "lacks a number"),
    (lambda r: write_pred(r, target_month="2026-09"), "not 2026-10"),
    (lambda r: write_pred(r, headline_yoy=6.5), "range does not contain"),
    (lambda r: write_pred(r, evidence_cutoff_utc="2099-01-01T00:00:00Z"), "in the future"),
    (lambda r: write_pred(r, evidence_cutoff_utc=None), "no evidence cutoff"),
    (lambda r: write_pred(r, evidence_cutoff_utc="2026-10-15T23:59:00"), "time zone"),
    (lambda r: (r / "results" / f"nowcast_{MONTH}.json").unlink(), "no prediction file"),
    (lambda r: (r / "data" / "official_releases.csv").write_text(
        "month,official_yoy,release_date,source_url\n2026-10,5.1,2026-11-12,x\n"), "already in data/official_releases"),
    (lambda r: ((r / "sealed").mkdir(), (r / "sealed" / f"{MONTH}.json").write_text("{}")), "already sealed"),
    (lambda r: git(r, "tag", f"seal-{MONTH}"), "already exists"),
])
def test_refuses_and_writes_nothing(repo, change, reason):
    change(repo)
    with pytest.raises(SM.Refuse, match=reason):
        dry(repo)
    assert not (repo / "sealed" / "dry-run").exists()


def test_refuses_2012_series_weights(repo):
    tidy = repo / "data" / "cpi_tidy.csv"
    rows = list(csv.DictReader(tidy.open(encoding="utf-8")))
    for r in rows:
        if r["code"] == "01":
            r["weight"] = "45.86"
    with tidy.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SM.Refuse, match="2012 series"):
        dry(repo)


def test_cli_rejects_bad_month_and_returns_1(capsys):
    assert SM.main(["2026-13", "--dry-run"]) == 1
    assert "[FAIL] not sealed" in capsys.readouterr().out


# ---------- score.py ----------
def official_division_contributions(month):
    tidy = O.load_tidy(ROOT / "data" / "cpi_tidy.csv")
    return SC.actual_contributions(month, tidy)


@pytest.fixture
def scored(repo):
    actual = official_division_contributions("2026-09")
    contrib = {c: v for c, v in actual.items()}
    contrib["01"] -= 0.5                      # sealed food contribution 0.5 pp too low -> the main surprise
    S.seal("2026-09", {"headline_yoy": 5.20, "range_low": 4.90, "range_high": 5.60, "contributions": contrib},
           seal_dir=repo / "sealed")
    S.seal(MONTH, {"headline_yoy": 5.31, "range_low": 4.86, "range_high": 5.82,
                  "contributors": [{"code": "01", "name": "Food and beverages", "pp": 2.71}]}, seal_dir=repo / "sealed")
    (repo / "data" / "official_releases.csv").write_text(
        "month,official_yoy,release_date,source_url\n2026-09,5.54,2026-10-12,https://www.mospi.gov.in/\n")
    return repo


def read_archive(repo):
    return {r["month"]: r for r in csv.DictReader((repo / "results" / "archive.csv").open(encoding="utf-8"))}


def test_score_fills_miss_range_and_main_surprise(scored):
    lines = []
    SC.score(root=scored, out=lines.append)
    a = read_archive(scored)
    sep = a["2026-09"]
    assert float(sep["miss_pp"]) == pytest.approx(5.20 - 5.54)
    assert sep["inside_range"] == "yes" and sep["seal_check"] == "PASS"
    assert sep["main_surprise"].startswith("Food and beverages added more than sealed")
    assert float(sep["main_surprise_pp"]) == pytest.approx(0.5)
    assert sep["release_date"] == "2026-10-12"
    assert a[MONTH]["main_surprise"] == "waiting for release" and a[MONTH]["official_yoy"] == ""
    assert any("miss -0.34 pp" in l for l in lines)


def test_score_outside_range_and_no_contributions(scored):
    (scored / "data" / "official_releases.csv").write_text(
        "month,official_yoy,release_date,source_url\n2026-10,6.10,2026-11-12,x\n")
    SC.score(root=scored, out=lambda *_: None)
    oct_ = read_archive(scored)[MONTH]
    assert oct_["inside_range"] == "no"
    assert "not available yet" in oct_["main_surprise"]     # no October indices in cpi_tidy.csv yet


def test_score_flags_a_tampered_seal_and_never_changes_it(scored):
    p = scored / "sealed" / "2026-09.json"
    p.write_text(p.read_text(encoding="utf-8").replace("5.2", "5.5"), encoding="utf-8")
    before = p.read_bytes()
    rows = SC.score(root=scored, out=lambda *_: None)
    assert next(r for r in rows if r["month"] == "2026-09")["seal_check"] == "FAIL"
    assert p.read_bytes() == before


def test_official_releases_file_has_headers_only():
    assert (ROOT / "data" / "official_releases.csv").read_text(encoding="utf-8").splitlines() == \
        [",".join(SC.RELEASE_FIELDS)]
