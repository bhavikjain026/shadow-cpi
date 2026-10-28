# How to check a Shadow CPI seal yourself

Before MoSPI publishes a month's CPI, Shadow CPI locks its experimental nowcast into one file,
`sealed/<month>.json`, and publishes that file's fingerprint (its SHA-256) in `sealed/<month>.sha256`.
If even one character of the file changed later, the fingerprint would no longer match.
The git tag `seal-<month>` and GitHub's own push record show **when** it was locked.
The seal proves when the forecast was committed, not what was read before it: the time lock (Tavily date filters,
re-checked in code) and `extract_as_of` address the evidence.

Below, October 2026 is the example. For another month, change `2026-10` everywhere.

## 1. Download the sealed file exactly as it was tagged

Open these two links (the `seal-2026-10` in the address means "as of the seal tag"), and save each with your
browser's *Save page as* (or right-click → *Save link as*):

- https://raw.githubusercontent.com/bhavikjain026/shadow-cpi/seal-2026-10/sealed/2026-10.json
- https://raw.githubusercontent.com/bhavikjain026/shadow-cpi/seal-2026-10/sealed/2026-10.sha256

Do not open the `.json` file in a text editor and save it again, because that can change spaces or line endings.

## 2. Recompute the fingerprint

Open a terminal in the folder where you saved the file, and run the command for your computer:

| Computer | Command |
| --- | --- |
| Mac | `shasum -a 256 2026-10.json` |
| Linux | `sha256sum 2026-10.json` |
| Windows (PowerShell) | `Get-FileHash 2026-10.json -Algorithm SHA256` |
| Any computer with Python | `python -c "import hashlib;print(hashlib.sha256(open('2026-10.json','rb').read()).hexdigest())"` |

It prints a 64-character code. Compare it with the text inside `2026-10.sha256` (Windows prints capital
letters; that is the same code).

- **Same code → PASS:** the file is exactly what was sealed.
- **Different code → FAIL:** the file is not the sealed one.

You can also read the file: `headline_yoy` is the nowcast, `range_low`/`range_high` the range,
`evidence_cutoff_utc` the last moment evidence was collected, and `code_commit` the exact code used.

## 3. Check when it was sealed

1. **The seal time written inside the file:** `sealed_at_utc`. This is written by our computer, so on its own it
   proves nothing; the next two checks are the independent ones.
2. **The tag on GitHub:** go to https://github.com/bhavikjain026/shadow-cpi/tags and find `seal-2026-10`.
   Click it to see the commit and its date.
3. **GitHub's push record (the strongest proof):** go to https://github.com/bhavikjain026/shadow-cpi/activity.
   GitHub's own servers record when each branch and tag was pushed; dates written inside git can be set by
   whoever makes the commit, but this push time cannot. Find the push that created the `seal-2026-10` tag and
   check that it is **before** MoSPI's release (12 Nov 2026, 4:00 pm IST = 10:30 UTC for October data).
4. **The Devpost copy:** the October SHA-256 is copied into the Devpost project description before submission.
   Devpost locks the description at the submission deadline (30 Oct 2026, 10:00 am Pacific), so the hash shown there
   was public before MoSPI's release. Compare it, character for character, with the hash you recomputed in step 2.
5. **Optional, an OpenTimestamps proof:** if `sealed/2026-10.json.ots` exists at the tag, it anchors the file's
   SHA-256 in a Bitcoin block. With the OpenTimestamps client (`pip install opentimestamps-client`), download both
   files from the tag and run `ots verify 2026-10.json.ots` next to `2026-10.json`: it prints the block time, which
   must be before the release. A proof that is still "pending" has not been anchored yet; try again a few hours
   after the seal. If there is no `.ots` file, rely on checks 2–4.

With git installed you can also check from a copy of the repository:

```
git clone https://github.com/bhavikjain026/shadow-cpi
cd shadow-cpi
git for-each-ref refs/tags/seal-2026-10 --format="tag created %(taggerdate:iso-strict)"
git show seal-2026-10:sealed/2026-10.json > check.json
sha256sum check.json          # Mac: shasum -a 256 check.json
```

**Which models were called:** `models_at_cutoff` in the sealed file names the Nemotron IDs in use on the evidence
cutoff day (Nebius retires the original IDs on 9 Nov 2026; later seals name the replacements;
`v2/PREREGISTRATION.md` Amendment G). `model_ids` holds the full dated map.

## 3b. The experimental v3 bundle (a separate check; v1's check above does not depend on it)

Right after v1's seal, the experimental v3 numbers (`v3/PREREG.md`) are sealed in `sealed/2026-10.v3.json`, and
`sealed/2026-10.bundle.sha256` lists the fingerprints of v1's file, v1's `.sha256` and the v3 file. Its tag is
`seal-2026-10-bundle`. From a copy of the repository, one command checks all three at the bundle tag and shows the
tag's date:

```
git checkout -q seal-2026-10-bundle && (cd sealed && shasum -a 256 -c 2026-10.bundle.sha256) && git for-each-ref refs/tags/seal-2026-10-bundle --format="tag created %(taggerdate:iso-strict)"
```

Linux: use `sha256sum -c` instead of `shasum -a 256 -c`. Three `OK` lines → PASS. The tag date must be before MoSPI's
release, and GitHub's push record (step 3) is again the strongest proof. Go back with `git checkout -q main`.

## 4. After the official release

`python score.py` compares each seal with the official number in `data/official_releases.csv` and writes
`results/archive.csv`: the miss, whether the official number fell inside the range, and the main surprise.
It also re-checks every fingerprint and reports PASS or FAIL. It never changes the sealed files.
