#!/usr/bin/env bash
# PESSOA weekly runner — wire to Windows Task Scheduler (Monday 06:00 local)
# Usage: bash cron/weekly.sh

set -euo pipefail

ROOT="/c/Users/user/porto-pessoa"
PY="$ROOT/.venv/Scripts/python.exe"
LOG="$ROOT/logs/weekly-$(date +%Y%m%d-%H%M).log"
export PYTHONIOENCODING=utf-8

cd "$ROOT"

echo "===== PESSOA weekly · $(date -Iseconds) =====" | tee -a "$LOG"

echo ">> FAROL scan" | tee -a "$LOG"
"$PY" -m pipeline.run_scan --type weekly 2>&1 | tee -a "$LOG"

echo ">> PESSOA deep analysis" | tee -a "$LOG"
"$PY" -m pipeline.pessoa_orchestrator --type weekly 2>&1 | tee -a "$LOG"

echo ">> Dashboard rebuild" | tee -a "$LOG"
"$PY" -m dashboard.generate 2>&1 | tee -a "$LOG"

echo ">> Notifications" | tee -a "$LOG"
"$PY" -m notify.send 2>&1 | tee -a "$LOG"

echo "===== DONE · $(date -Iseconds) =====" | tee -a "$LOG"
