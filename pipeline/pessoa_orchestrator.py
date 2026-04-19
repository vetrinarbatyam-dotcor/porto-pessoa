"""PESSOA · orchestrator — runs the 5-sub-agent deep analysis on Crivo candidates.

Each property gets analyzed by invoking the existing `/portugal-property` skill
via the Claude CLI, which returns a JSON bundle we persist in `scores`.

Strategy:
- For each candidate property, build a context pack (address, price, m², URLs)
- Run `claude -p "<prompt>" --output-format json` with the PESSOA instructions
- Parse scores A/B/C/D/E + composite + verdict + summary
- Store in `scores` table
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, PESSOA_TOP_N_INITIAL, PESSOA_TOP_N_WEEKLY
from pipeline.crivo import pick_candidates


CLAUDE_CMD = "claude"  # Claude Code CLI must be on PATH


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _load_property(pid: int) -> dict:
    with _conn() as db:
        prop = db.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
        listings = db.execute("SELECT source, url, asking_price FROM listings WHERE property_id=?", (pid,)).fetchall()
    return {
        "property": dict(prop),
        "listings": [dict(l) for l in listings],
    }


def _build_prompt(pack: dict) -> str:
    p = pack["property"]
    urls = "\n".join(f"- {l['source']}: {l['url']}" for l in pack["listings"])
    return textwrap.dedent(f"""
    Run the `/portugal-property` skill on the following Porto property.

    Context:
    - Address: {p['address']}
    - Freguesia: {p['freguesia']}
    - Typology: {p['typology']}
    - Area: {p['area_m2']} m²
    - Asking price: €{p['price_eur']}
    - €/m²: {p['price_per_m2']}
    - Built: {p['built_year'] or 'unknown'}
    - Energy cert: {p['energy_cert'] or 'unknown'}

    Sources:
    {urls}

    Execute the full 5-sub-agent deep analysis (A Financial, B Structural, C Legal, D Location, E Risk).
    Then output a JSON block inside <json>...</json> tags with exactly this shape:

    {{
      "score_a": <0-10 number>,
      "score_b": <0-10 number>,
      "score_c": <0-10 number>,
      "score_d": <0-10 number>,
      "score_e": <0-10 number>,
      "composite": <0-10 number>,
      "verdict": "strong_buy|buy|hold|pass|strong_pass",
      "summary_md": "<brief Hebrew markdown summary, 3-5 bullets>",
      "agent_a": "<bullet findings Financial>",
      "agent_b": "<bullet findings Structural>",
      "agent_c": "<bullet findings Legal>",
      "agent_d": "<bullet findings Location>",
      "agent_e": "<bullet findings Risk>"
    }}

    Nothing else outside the <json>...</json> block.
    """).strip()


def _invoke_claude(prompt: str, timeout: int = 300) -> str:
    """Call Claude CLI headless. Returns stdout text."""
    cmd = [CLAUDE_CMD, "-p", prompt, "--permission-mode", "bypassPermissions"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
        return r.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "`claude` CLI not found on PATH. Install Claude Code or set CLAUDE_CMD env var."
        )


def _parse_json_block(text: str) -> dict:
    m = re.search(r"<json>\s*(\{.*?\})\s*</json>", text, re.S)
    if not m:
        raise ValueError("No <json>...</json> block in model output")
    return json.loads(m.group(1))


def analyze_one(pid: int) -> bool:
    """Score one property. Returns True on success."""
    pack = _load_property(pid)
    print(f"[pessoa] analyzing #{pid} · {pack['property']['typology']} {pack['property']['address'][:50]}")
    prompt = _build_prompt(pack)
    out = _invoke_claude(prompt)
    try:
        data = _parse_json_block(out)
    except Exception as e:
        print(f"[pessoa] #{pid} parse FAIL: {e}")
        return False

    with _conn() as db:
        db.execute(
            """INSERT INTO scores
               (property_id, score_a, score_b, score_c, score_d, score_e,
                composite, verdict, summary_md,
                agent_a_json, agent_b_json, agent_c_json, agent_d_json, agent_e_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                pid, data["score_a"], data["score_b"], data["score_c"],
                data["score_d"], data["score_e"], data["composite"], data["verdict"],
                data.get("summary_md", ""),
                data.get("agent_a", ""), data.get("agent_b", ""),
                data.get("agent_c", ""), data.get("agent_d", ""), data.get("agent_e", ""),
            ),
        )
        db.commit()
    print(f"[pessoa] #{pid} · composite {data['composite']} · {data['verdict']}")
    return True


def run(top_n: int, dry_run: bool = False) -> dict:
    pids = pick_candidates(top_n=top_n, only_unscored=True)
    stats = {"attempted": len(pids), "succeeded": 0, "failed": 0}
    for pid in pids:
        if dry_run:
            print(f"[dry-run] would analyze #{pid}")
            continue
        try:
            ok = analyze_one(pid)
            stats["succeeded" if ok else "failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            print(f"[pessoa] #{pid} ERROR: {e}")
    return stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["initial", "weekly"], default="weekly")
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    top = args.top or (PESSOA_TOP_N_INITIAL if args.type == "initial" else PESSOA_TOP_N_WEEKLY)
    stats = run(top_n=top, dry_run=args.dry_run)
    print(f"[pessoa] {stats}")


if __name__ == "__main__":
    main()
