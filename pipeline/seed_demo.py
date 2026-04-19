"""Seed demo data so the dashboard has something to show before first real scan."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from random import uniform, choice, randint

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, FREGUESIAS

DEMOS = [
    # (freguesia, typology, area, price, built, energy, floor, addr)
    ("Sé",              "T2", 82, 445_000, 1965, "D", "2º", "Rua do Infante 45"),
    ("Miragaia",        "T2", 78, 398_000, 1955, "E", "1º", "Rua de Miragaia 120"),
    ("Cedofeita",       "T1", 55, 285_000, 1978, "C", "3º", "Rua de Cedofeita 203"),
    ("Cedofeita",       "T3", 105, 625_000, 2010, "B", "5º", "Rua Álvares Cabral 87"),
    ("Santo Ildefonso", "T2", 72, 355_000, 1970, "D", "2º", "Rua Santa Catarina 301"),
    ("São Nicolau",     "T1", 48, 295_000, 1930, "F", "3º", "Rua Escura 18"),
    ("Vitória",         "T2", 88, 410_000, 1968, "D", "4º", "Rua Cândido dos Reis 22"),
    ("Sé",              "T3", 115, 590_000, 1960, "E", "2º", "Rua de S. João 55"),
    ("Cedofeita",       "T2", 80, 420_000, 1985, "C", "4º", "Rua do Rosário 14"),
    ("Bonfim-West",     "T1", 52, 225_000, 1975, "D", "1º", "Rua do Heroísmo 88"),
    ("Santo Ildefonso", "T0", 35, 185_000, 1965, "E", "2º", "Rua Alexandre Braga 12"),
    ("Miragaia",        "T3", 110, 615_000, 2005, "B", "3º", "Rua do Ouro 77"),
]
SOURCE_MIX = [
    ["idealista", "imovirtual", "casa_sapo"],
    ["idealista", "custojusto"],
    ["imovirtual", "casa_sapo", "supercasa"],
    ["idealista", "imovirtual", "casa_sapo", "supercasa"],
    ["casa_sapo", "custojusto"],
    ["idealista"],
    ["idealista", "imovirtual"],
    ["imovirtual", "supercasa", "custojusto"],
    ["idealista", "casa_sapo", "supercasa"],
    ["custojusto"],
    ["idealista", "supercasa"],
    ["idealista", "imovirtual", "casa_sapo", "supercasa", "custojusto"],
]

SCORES_DEMO = [
    # (a, b, c, d, e, verdict)
    (7.8, 6.8, 7.5, 8.4, 7.1, "buy"),
    (7.2, 5.5, 6.0, 8.2, 6.4, "hold"),
    (8.1, 7.9, 8.3, 7.6, 7.8, "buy"),
    (6.5, 8.9, 8.0, 7.2, 7.0, "hold"),
    (7.5, 6.2, 6.8, 8.0, 6.9, "hold"),
    (6.0, 4.5, 5.5, 7.8, 5.8, "hold"),
    (7.0, 7.1, 7.2, 7.9, 7.0, "buy"),
    (5.8, 5.9, 5.5, 7.4, 5.5, "hold"),
    (7.4, 7.0, 7.3, 8.1, 7.2, "buy"),
    (6.8, 5.8, 6.5, 7.0, 6.3, "hold"),
    (5.5, 4.8, 5.0, 6.8, 5.0, "pass"),
    (7.9, 8.2, 7.8, 8.5, 7.6, "strong_buy"),
]


def composite(a, b, c, d, e):
    return round(a * 0.25 + b * 0.20 + c * 0.25 + d * 0.20 + e * 0.10, 2)


def seed():
    with sqlite3.connect(DB_PATH) as db:
        cur = db.cursor()
        for i, (freg, typ, area, price, built, energy, floor, addr) in enumerate(DEMOS):
            psm = round(price / area, 1)
            chash = hashlib.sha1(f"{addr}|{typ}|{area}|{price//5000*5000}".encode()).hexdigest()[:16]
            cur.execute(
                """INSERT OR IGNORE INTO properties
                   (canonical_hash, address, freguesia, typology, area_m2, price_eur, price_per_m2,
                    built_year, energy_cert, floor, description, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (chash, addr, freg, typ, area, price, psm, built, energy, floor,
                 f"דירת {typ} ב-{freg} · דמו seed", json.dumps({"demo": True})),
            )
            pid = cur.lastrowid
            if not pid:
                continue

            for src in SOURCE_MIX[i]:
                sample_url = f"https://{src.replace('_','.')}.example/{pid}-{src}-demo"
                cur.execute(
                    """INSERT OR IGNORE INTO listings (property_id, source, external_id, url, asking_price, days_on_market)
                       VALUES (?,?,?,?,?,?)""",
                    (pid, src, f"{src}-{pid}", sample_url, price, randint(7, 90)),
                )

            a, b, c, d, e, verdict = SCORES_DEMO[i]
            comp = composite(a, b, c, d, e)
            cur.execute(
                """INSERT INTO scores
                   (property_id, score_a, score_b, score_c, score_d, score_e, composite, verdict, summary_md,
                    agent_a_json, agent_b_json, agent_c_json, agent_d_json, agent_e_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, a, b, c, d, e, comp, verdict,
                 f"דוגמה · נותח ב-{freg} במחיר €{price:,} · ציון {comp}",
                 f"עלות רכישה כוללת ~€{int(price*1.069):,}\nתשואה LTR ~{round(uniform(3.0, 5.5), 1)}%\nתשואה AL היברידי ~{round(uniform(5.0, 7.5), 1)}%",
                 f"בניין משנת {built} · דירוג {energy}\nרמת שיפוץ: {choice(['קוסמטי','קל','בינוני','מלא'])}\nחלונות/חשמל ישנים סבירים",
                 f"freguesia {freg} לא ב-zone contenção AL\nCertidão Permanente טרם נבדק\nLicença de Utilização נדרש אימות",
                 f"מטרו קרוב · מנועי ביקוש: אטרקציות תיירות + אוניברסיטה\nג'נטריפיקציה: שלב מתקדם\nתשואה נזילה ליציאה",
                 f"DOM {randint(20,110)} · ללא הורדות מחיר\nסיכון רגולטורי AL ברקע\nתזה לא תלויה ב-AL יחיד"),
            )
        db.commit()
    print(f"[seed] seeded {len(DEMOS)} demo properties with listings + scores")


if __name__ == "__main__":
    seed()
