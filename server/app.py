"""PESSOA Control Server — local Flask API for dashboard buttons.

Endpoints:
  GET  /api/status           — scan state, last run, scheduled hour
  POST /api/scan/start       — kick off FAROL scan in background
  POST /api/schedule         — set nightly Windows task (body: {hour: 0-23})
  DELETE /api/schedule       — remove nightly task

Run: .venv/Scripts/python.exe server/app.py   (or double-click start_server.bat)
Listens on http://127.0.0.1:5055
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).parent.parent
STATE_FILE = ROOT / "server" / "state.json"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TASK_NAME = "PESSOA-Nightly-Porto"

app = Flask(__name__)
CORS(app)  # allow file:// dashboard to call us


def get_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"running": False, "last_scan": None, "last_count": 0, "schedule_hour": None, "log_tail": ""}


def set_state(**updates):
    s = get_state()
    s.update(updates)
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_thread(pages: int = 3):
    set_state(running=True, started_at=time.time(), error=None)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(
            [PY, "-m", "pipeline.run_scan", "--type", "weekly", "--pages", str(pages)],
            cwd=ROOT, capture_output=True, text=True, timeout=900, env=env, encoding="utf-8",
        )
        # Count new properties from stdout
        import re
        m = re.search(r"(\d+)\s+new", r.stdout or "")
        new_count = int(m.group(1)) if m else 0
        # Regenerate dashboard
        subprocess.run([PY, "-m", "dashboard.generate"], cwd=ROOT, env=env, capture_output=True, encoding="utf-8")
        set_state(
            running=False, last_scan=time.time(), last_count=new_count,
            log_tail=(r.stdout or "")[-800:],
        )
    except subprocess.TimeoutExpired:
        set_state(running=False, error="scan timeout after 15min")
    except Exception as e:
        set_state(running=False, error=str(e))


@app.get("/api/status")
def status():
    s = get_state()
    # Enrich with computed fields
    if s.get("last_scan"):
        s["last_scan_ago_s"] = int(time.time() - s["last_scan"])
    return jsonify(s)


@app.post("/api/scan/start")
def scan_start():
    s = get_state()
    if s.get("running"):
        return jsonify({"error": "scan already running"}), 409
    pages = int(request.json.get("pages", 3)) if request.is_json else 3
    threading.Thread(target=scan_thread, args=(pages,), daemon=True).start()
    return jsonify({"ok": True, "pages": pages})


@app.post("/api/schedule")
def schedule_set():
    data = request.get_json() or {}
    hour = int(data.get("hour", 3))
    if not 0 <= hour <= 23:
        return jsonify({"error": "hour must be 0-23"}), 400

    time_str = f"{hour:02d}:00"
    bash = "C:\\Program Files\\Git\\bin\\bash.exe"
    script = str(ROOT / "cron" / "weekly.sh").replace("/", "\\")

    # Remove existing task (ignore errors)
    subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
                   capture_output=True, shell=False)
    # Create daily task
    tr = f'\"{bash}\" \"{script}\"'
    r = subprocess.run(
        ["schtasks", "/create", "/sc", "daily", "/tn", TASK_NAME,
         "/tr", tr, "/st", time_str, "/f"],
        capture_output=True, text=True, shell=False,
    )
    if r.returncode != 0:
        return jsonify({"error": (r.stderr or r.stdout or "schtasks failed").strip()}), 500
    set_state(schedule_hour=hour)
    return jsonify({"ok": True, "hour": hour, "time": time_str})


@app.delete("/api/schedule")
def schedule_remove():
    subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
                   capture_output=True, shell=False)
    set_state(schedule_hour=None)
    return jsonify({"ok": True})


@app.get("/api/ping")
def ping():
    return jsonify({"ok": True, "version": "1.0"})


if __name__ == "__main__":
    print("PESSOA control server running at http://127.0.0.1:5055", flush=True)
    app.run(host="127.0.0.1", port=5055, debug=False, use_reloader=False)
