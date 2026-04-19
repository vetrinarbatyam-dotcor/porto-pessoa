"""Re-tag freguesia on existing DB properties using their listing URLs.

After expanding FREGUESIAS in config, run this to fix mis-tagged properties.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH
from scrapers.base import infer_freguesia


def retag():
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        props = db.execute("SELECT id, address, freguesia FROM properties").fetchall()
        changed = 0
        now_in_scope = 0
        for p in props:
            # Collect all URLs for this property
            urls = [r["url"] for r in db.execute(
                "SELECT url FROM listings WHERE property_id=?", (p["id"],)
            ).fetchall()]
            # Try to infer better freguesia from URL first
            best = ""
            for u in urls:
                freg = infer_freguesia("", u)
                if freg:
                    best = freg
                    break
            if not best:
                best = infer_freguesia(p["address"] or "")
            if best and best != p["freguesia"]:
                db.execute("UPDATE properties SET freguesia=? WHERE id=?", (best, p["id"]))
                changed += 1
            if best:
                now_in_scope += 1
        db.commit()
        print(f"Re-tagged {changed}/{len(props)} · {now_in_scope}/{len(props)} now have recognized freguesia")

        print("\nBy freguesia after re-tag:")
        for r in db.execute(
            "SELECT COALESCE(freguesia, '(none)') f, COUNT(*) c FROM properties GROUP BY f ORDER BY c DESC"
        ):
            print(f"  {r['f']}: {r['c']}")


if __name__ == "__main__":
    retag()
