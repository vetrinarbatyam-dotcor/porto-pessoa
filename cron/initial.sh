#!/usr/bin/env bash
# PESSOA one-shot initial 30-day backfill. Run manually once.
set -euo pipefail

ROOT="/c/Users/user/porto-pessoa"
PY="$ROOT/.venv/Scripts/python.exe"
LOG="$ROOT/logs/initial-$(date +%Y%m%d-%H%M).log"
export PYTHONIOENCODING=utf-8

cd "$ROOT"

echo "===== PESSOA INITIAL 30d · $(date -Iseconds) =====" | tee -a "$LOG"

echo ">> FAROL scan (5 sources, 30d backfill)" | tee -a "$LOG"
"$PY" -m pipeline.run_scan --type initial --pages 20 2>&1 | tee -a "$LOG"

echo ">> PESSOA deep on top 50" | tee -a "$LOG"
"$PY" -m pipeline.pessoa_orchestrator --type initial --top 50 2>&1 | tee -a "$LOG"

echo ">> Dashboard rebuild" | tee -a "$LOG"
"$PY" -m dashboard.generate 2>&1 | tee -a "$LOG"

echo "===== DONE · $(date -Iseconds) =====" | tee -a "$LOG"
echo "Open the dashboard: file:///C:/Users/user/porto-pessoa/dashboard/out/index.html"
