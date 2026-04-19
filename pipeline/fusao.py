"""Fusão · sub-agent 5 — dedup & merge across the 5 sources.

Matching strategy:
1. Exact URL → same listing re-scraped (update last_seen).
2. Same canonical_hash (normalized address + typology + area + price bucket) → same property on different site.
3. Fuzzy fallback: price ±5%, area ±2 m², typology match, fuzz(address) ≥ 88 → same property.
"""
import json
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, DEDUP_PRICE_TOL, DEDUP_AREA_TOL_M2, DEDUP_ADDRESS_FUZZ
from scrapers.base import RawListing

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _fuzzy_match(new: RawListing, cand: sqlite3.Row) -> bool:
    if not new.typology or not cand["typology"]:
        return False
    if new.typology != cand["typology"]:
        return False
    if cand["price_eur"] and new.price_eur:
        rel = abs(new.price_eur - cand["price_eur"]) / cand["price_eur"]
        if rel > DEDUP_PRICE_TOL:
            return False
    if cand["area_m2"] and new.area_m2:
        if abs(new.area_m2 - cand["area_m2"]) > DEDUP_AREA_TOL_M2:
            return False
    if fuzz and new.address and cand["address"]:
        if fuzz.token_set_ratio(new.address.lower(), cand["address"].lower()) < DEDUP_ADDRESS_FUZZ:
            return False
    return True


def upsert(raw_listings: Iterable[RawListing]) -> dict:
    """Insert/merge raw listings into DB. Returns counts."""
    stats = {"inserted_properties": 0, "inserted_listings": 0, "updated_listings": 0, "skipped_oos": 0}
    with _conn() as db:
        cur = db.cursor()
        for raw in raw_listings:
            if not raw.in_scope():
                stats["skipped_oos"] += 1
                continue

            # (a) URL already known?
            cur.execute("SELECT id, property_id FROM listings WHERE source=? AND url=?", (raw.source, raw.url))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE listings SET last_seen=CURRENT_TIMESTAMP, asking_price=? WHERE id=?",
                    (raw.price_eur, row["id"]),
                )
                cur.execute("UPDATE properties SET last_seen=CURRENT_TIMESTAMP WHERE id=?", (row["property_id"],))
                stats["updated_listings"] += 1
                continue

            # (b) Canonical hash match?
            chash = raw.canonical_hash()
            cur.execute("SELECT id FROM properties WHERE canonical_hash=?", (chash,))
            row = cur.fetchone()
            prop_id = row["id"] if row else None

            # (c) Fuzzy match within same typology+price band
            if not prop_id:
                cur.execute(
                    "SELECT id, address, typology, area_m2, price_eur FROM properties "
                    "WHERE typology=? AND ABS(price_eur-?) < ?",
                    (raw.typology, raw.price_eur, raw.price_eur * DEDUP_PRICE_TOL if raw.price_eur else 99_999_999),
                )
                for cand in cur.fetchall():
                    if _fuzzy_match(raw, cand):
                        prop_id = cand["id"]
                        break

            # Insert new property if still no match
            if not prop_id:
                cur.execute(
                    """INSERT INTO properties
                       (canonical_hash, address, freguesia, typology, area_m2, price_eur,
                        price_per_m2, built_year, energy_cert, floor, condominio_eur,
                        description, photo_url, raw_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        chash, raw.address, raw.freguesia, raw.typology, raw.area_m2, raw.price_eur,
                        raw.price_per_m2(), raw.built_year, raw.energy_cert, raw.floor, raw.condominio_eur,
                        raw.description, raw.photo_url, json.dumps(raw.raw, ensure_ascii=False)
                    ),
                )
                prop_id = cur.lastrowid
                stats["inserted_properties"] += 1

            # Insert the listing occurrence
            cur.execute(
                """INSERT OR IGNORE INTO listings (property_id, source, external_id, url, asking_price)
                   VALUES (?,?,?,?,?)""",
                (prop_id, raw.source, raw.external_id, raw.url, raw.price_eur),
            )
            if cur.rowcount:
                stats["inserted_listings"] += 1

        db.commit()
    return stats
