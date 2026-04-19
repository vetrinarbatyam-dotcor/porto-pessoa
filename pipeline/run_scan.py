"""FAROL · main entry point — orchestrates 5 scrapers → Fusão → Crivo."""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, SOURCES, BUDGET_MIN, BUDGET_MAX, PAGES_PER_SOURCE
from pipeline.fusao import upsert
from pipeline.crivo import pick_candidates

from scrapers.idealista import IdealistaScraper
from scrapers.imovirtual import ImovirtualScraper
from scrapers.casa_sapo import CasaSapoScraper
from scrapers.supercasa import SupercasaScraper
from scrapers.custojusto import CustojustoScraper

SCRAPERS = {
    "idealista":  IdealistaScraper,
    "imovirtual": ImovirtualScraper,
    "casa_sapo":  CasaSapoScraper,
    "supercasa":  SupercasaScraper,
    "custojusto": CustojustoScraper,
}


def _open_scan(scan_type: str) -> int:
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute("INSERT INTO scans (scan_type, status) VALUES (?, 'running')", (scan_type,))
        return cur.lastrowid


def _close_scan(scan_id: int, raw_count: int, new_props: int, status: str, notes: str = ""):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "UPDATE scans SET finished_at=CURRENT_TIMESTAMP, raw_fetched=?, new_properties=?, "
            "status=?, notes=? WHERE id=?",
            (raw_count, new_props, status, notes, scan_id),
        )


def run(sources: list[str], scan_type: str, pages: int) -> dict:
    scan_id = _open_scan(scan_type)
    all_raw = []
    errors = []
    for src in sources:
        cls = SCRAPERS[src]
        scr = cls(max_pages=pages)
        try:
            got = list(scr.scrape(BUDGET_MIN, BUDGET_MAX))
            print(f"[{src}] collected {len(got)} raw listings")
            all_raw.extend(got)
        except Exception as e:
            errors.append(f"{src}: {e}")
            print(f"[{src}] ERROR: {e}")

    stats = upsert(all_raw)
    print(f"[fusao] {stats}")

    _close_scan(
        scan_id, raw_count=len(all_raw), new_props=stats["inserted_properties"],
        status="partial" if errors else "ok", notes="; ".join(errors),
    )
    print(f"[scan {scan_id}] done · {stats['inserted_properties']} new · {len(errors)} source errors")
    return stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["initial", "weekly"], default="weekly")
    p.add_argument("--sources", nargs="+", default=SOURCES, choices=SOURCES)
    p.add_argument("--pages", type=int, default=PAGES_PER_SOURCE)
    args = p.parse_args()
    run(args.sources, args.type, args.pages)


if __name__ == "__main__":
    main()
