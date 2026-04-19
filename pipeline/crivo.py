"""Crivo · sub-agent 6 — triage before PESSOA deep analysis.

Picks top N candidates for full 5-sub-agent analysis. Heuristic pre-score:
- Price/m² vs freguesia median (closer to median = more "real", far outlier = filtered)
- Multi-source (same property on 2+ boards = higher signal)
- Typology preference (T1-T2 slight boost for AL thesis)
- Penalize missing critical data (area=0, no freguesia)
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, FREGUESIA_MEDIANS_EUR_PER_M2, CRIVO_PRICE_M2_TOLERANCE


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def triage_score(row: sqlite3.Row) -> float:
    """Heuristic pre-score 0-10 for selection, NOT the final PESSOA composite."""
    if not row["area_m2"] or not row["price_eur"] or not row["freguesia"]:
        return 0.0

    psm = row["price_per_m2"] or 0
    median = FREGUESIA_MEDIANS_EUR_PER_M2.get(row["freguesia"], 4500)
    deviation = abs(psm - median) / median if median else 1.0
    if deviation > CRIVO_PRICE_M2_TOLERANCE:
        return 0.0  # filtered — suspicious pricing

    # Score ingredients
    price_fit = max(0, 1.0 - deviation * 2)          # 1.0 at median, 0 at ±50%
    typology_fit = {"T0": 0.6, "T1": 0.9, "T2": 1.0, "T3": 0.85}.get(row["typology"], 0.5)
    multi_source = min(1.0, (row["source_count"] or 1) / 3)  # bonus up to 3 sources
    freshness_fit = 0.8  # placeholder; could parse days_on_market later

    return round(10 * (price_fit * 0.4 + typology_fit * 0.2 + multi_source * 0.25 + freshness_fit * 0.15), 2)


def pick_candidates(top_n: int = 50, only_unscored: bool = True) -> list[int]:
    """Return property_ids ranked by triage_score."""
    with _conn() as db:
        sql = """
            SELECT p.id, p.address, p.freguesia, p.typology, p.area_m2, p.price_eur, p.price_per_m2,
                   (SELECT COUNT(*) FROM listings l WHERE l.property_id=p.id) AS source_count
            FROM properties p
            WHERE p.status='active'
        """
        if only_unscored:
            sql += " AND NOT EXISTS (SELECT 1 FROM scores s WHERE s.property_id=p.id)"
        rows = db.execute(sql).fetchall()

    ranked = sorted(
        ((triage_score(r), r["id"]) for r in rows),
        key=lambda t: t[0], reverse=True
    )
    picked = [pid for score, pid in ranked if score > 0][:top_n]
    print(f"[crivo] {len(rows)} candidates → {len(picked)} picked (top {top_n})")
    return picked
