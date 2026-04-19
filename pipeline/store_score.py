"""Helper — store a PESSOA JSON result into the scores table.

Usage: echo '<json>' | python -m pipeline.store_score <property_id>
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def store(pid: int, payload: dict):
    a = float(payload["score_a"]); b = float(payload["score_b"])
    c = float(payload["score_c"]); d = float(payload["score_d"]); e = float(payload["score_e"])
    comp = float(payload.get("composite", round(a*0.25+b*0.20+c*0.25+d*0.20+e*0.10, 2)))
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """INSERT INTO scores
               (property_id, score_a, score_b, score_c, score_d, score_e,
                composite, verdict, summary_md,
                agent_a_json, agent_b_json, agent_c_json, agent_d_json, agent_e_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, a, b, c, d, e, comp, payload.get("verdict", "hold"),
             payload.get("summary_md", ""),
             payload.get("agent_a", ""), payload.get("agent_b", ""),
             payload.get("agent_c", ""), payload.get("agent_d", ""), payload.get("agent_e", "")),
        )
        db.commit()
    print(f"[pessoa] stored score for #{pid} · composite {comp}")


def main():
    pid = int(sys.argv[1])
    payload = json.loads(sys.stdin.read())
    store(pid, payload)


if __name__ == "__main__":
    main()
