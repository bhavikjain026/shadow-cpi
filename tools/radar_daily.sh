#!/bin/zsh
# One daily radar run (v2/RADAR_PREREG.md), started by launchd at 10:07 IST on 27, 28 and 29 Oct 2026
# (~/Library/LaunchAgents/in.shadowcpi.radar-daily.plist). Never freezes the radar: freezing needs the owner's OK.
#   1. stop if another radar run is going (lock + process check)
#   2. git pull --no-rebase origin main
#   3. stop if the whole-word bug fixes (Amendments R2 and R3) are not logged in RADAR_PREREG.md, or the date is not a run day
#   4. stop if the radar budget (cap read from config/budget.json) is used up
#   5. python -m v2.radar once, under caffeinate
#   6. after the radar: page drift (python -m v2.drift) and the radar skeptic (python -m v2.radar_skeptic),
#      v2/DRIFT_PREREG.md, each under its own cap; a failure there is reported but never undoes the radar step
#   7. commit the radar, drift and skeptic files and the credit ledger, push
#   8. a 3-line report in logs/radar_daily_<date>.txt and a macOS notification
set -u
REPO="/Users/bhavikjain/NVIDIA HACKATHON/shadow-cpi"
cd "$REPO" || exit 1
DAY=$(TZ=Asia/Kolkata date +%Y-%m-%d)
LOG="logs/radar_daily_$DAY.txt"
LOCK="/tmp/shadow-cpi-radar.lock"
mkdir -p logs

report() {    # three lines: what happened, credits, next
  printf '%s\n%s\n%s\n' "$1" "$2" "$3" > "$LOG.report"
  cat "$LOG.report" >> "$LOG"
  /usr/bin/osascript -e "display notification \"$1 | $2\" with title \"Shadow CPI radar $DAY\"" 2>/dev/null
  exit "${4:-0}"
}

exec >>"$LOG" 2>&1
echo "=== $(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S IST') radar daily run"

case "$DAY" in 2026-10-27|2026-10-28|2026-10-29) ;; *) report "SKIPPED: $DAY is not a radar run day" "credits: none used" "next: nothing scheduled";; esac

if ! mkdir "$LOCK" 2>/dev/null || pgrep -f "v2.radar" >/dev/null; then
  report "SKIPPED: another radar run is going (lock $LOCK or a v2.radar process)" "credits: none used" "next: check the other run's log"
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

git pull --no-rebase origin main || report "FAILED: git pull --no-rebase origin main (see $LOG)" "credits: none used" "next: fix the repo state by hand" 1

for AMEND in R2 R3; do
  if ! grep -q "Amendment $AMEND (logged bug fix)" v2/RADAR_PREREG.md; then
    report "SKIPPED: the whole-word bug fix (Amendment $AMEND) is not on main; no run with the old matching" "credits: none used" "next: push the fix, the next run day picks it up"
  fi
done

source .venv/bin/activate
LEFT=$(python - <<'EOF'
import json
from shadow_cpi.budget import spent
cap = json.load(open("config/budget.json"))["caps"]["radar-2026-10"]
used = spent("radar-2026-10")
print(f"{used} {cap} {cap - used}")
EOF
) || report "FAILED: could not read the radar budget" "credits: none used" "next: check config/budget.json and the ledger" 1
read USED CAP REMAIN <<< "$LEFT"
# after the radar (v2/DRIFT_PREREG.md): page drift, then the skeptic; descriptive only, separate caps.
# Sets EXTRA (one summary line) and DS (credits the two spent); a failure here never undoes the radar step.
side_spent() { python -c "from shadow_cpi.budget import spent; print(spent('drift-2026-10') + spent('radar-skeptic-2026-10'))"; }
after_radar() {
  local before=$(side_spent)
  if grep -q "pre-registration" v2/DRIFT_PREREG.md 2>/dev/null; then
    caffeinate -i python -m v2.drift && EXTRA="drift $(python -c "
import json; r = json.load(open('v2/radar/drift_2026-10.json'))['runs'][-1]
print(f\"{r['changed']} of {r['checked']} pages changed\")")" || EXTRA="drift FAILED"
    caffeinate -i python -m v2.radar_skeptic && EXTRA="$EXTRA; skeptic $(python -c "
import json; e = json.load(open('v2/radar/skeptic_2026-10.json'))['events']
print(f\"{sum(bool(v['challenged']) for v in e.values())} of {len(e)} events challenged\")")" || EXTRA="$EXTRA; skeptic FAILED"
  else
    EXTRA="drift and skeptic SKIPPED: v2/DRIFT_PREREG.md not on main"
  fi
  DS=$(( $(side_spent) - before ))
}
add_side_files() { for F in v2/radar/drift_2026-10.json v2/radar/skeptic_2026-10.json; do [ -f "$F" ] && git add "$F"; done; }

if [ "$REMAIN" -le 0 ]; then              # no radar run, but drift and skeptic have their own caps
  after_radar
  git add results/credit_ledger.jsonl; add_side_files
  git commit -m "Drift and skeptic $DAY (radar budget used up): $EXTRA ($DS credits)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && git push origin main
  report "SKIPPED radar: budget used up ($USED of $CAP); $EXTRA" "credits: radar none; drift+skeptic $DS" "next: freeze at 29 Oct 23:59 IST needs the owner's OK"
fi

caffeinate -i python -m v2.radar
RC=$?
AFTER=$(python -c "from shadow_cpi.budget import spent; print(spent('radar-2026-10'))")
SUMMARY=$(python - <<'EOF'
import json
d = json.load(open("v2/radar/radar_2026-10.json"))
ev = d.get("events", [])
r = d["runs"][-1] if d.get("runs") else {}
print(f"{len(ev)} events, {sum(e['tier'] == 'corroborated' for e in ev)} corroborated; run {len(d.get('runs', []))} "
      f"{'complete' if r.get('complete') else 'INCOMPLETE'}")
EOF
)
[ $RC -ne 0 ] && report "FAILED: python -m v2.radar exit $RC; $SUMMARY" "credits: $((AFTER - USED)) this run, radar $AFTER of $CAP" "next: read $LOG; nothing committed" 1

after_radar
SUMMARY="$SUMMARY; $EXTRA"

git add v2/radar/radar_2026-10.json results/credit_ledger.jsonl
add_side_files
git commit -m "Radar 2026-10 daily run $DAY: $SUMMARY ($((AFTER - USED)) radar credits, radar total $AFTER of $CAP; drift+skeptic $DS)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || report "FAILED: commit ($SUMMARY)" "credits: $((AFTER - USED)) this run, radar $AFTER of $CAP" "next: commit by hand" 1
git push origin main || report "RAN but push FAILED: $SUMMARY (committed locally)" "credits: $((AFTER - USED)) this run, radar $AFTER of $CAP" "next: git pull --no-rebase origin main && git push" 1
report "DONE: $SUMMARY; pushed $(git rev-parse --short HEAD)" "credits: $((AFTER - USED)) this run, radar $AFTER of $CAP; drift+skeptic $DS" "next: $([ "$DAY" = 2026-10-29 ] && echo 'freeze at 29 Oct 23:59 IST needs the owner OK' || echo 'next run tomorrow 10:07 IST')"
