"""Generate weekly summary payload (text + HTML) from DB."""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, NOTIFY_THRESHOLD_COMPOSITE


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def build() -> dict:
    """Return dict with `text` (WhatsApp-friendly) and `html` (Gmail) summary."""
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    with _conn() as db:
        new_count = db.execute(
            "SELECT COUNT(*) AS c FROM properties WHERE first_seen >= ?",
            (week_ago,),
        ).fetchone()["c"]

        top = db.execute(
            "SELECT * FROM v_top_properties WHERE composite >= ? ORDER BY composite DESC LIMIT 5",
            (NOTIFY_THRESHOLD_COMPOSITE,),
        ).fetchall()

        last_scan = db.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()

    date_str = datetime.now().strftime("%d/%m/%Y")
    wa_lines = [
        f"🏛️ *PESSOA · פורטו מרכז* · {date_str}",
        "",
        f"📊 סריקה שבועית הסתיימה",
        f"• {new_count} נכסים חדשים השבוע",
        f"• {len(top)} עברו סף {NOTIFY_THRESHOLD_COMPOSITE} מצרפי",
        "",
    ]
    if top:
        wa_lines.append("🏆 *הטופ 5:*")
        for i, r in enumerate(top, 1):
            wa_lines.append(
                f"{i}. {r['typology']} {r['freguesia']} · {r['area_m2']}m² · €{r['price_eur']:,} · *{r['composite']:.1f}*"
            )
        wa_lines.append("")
    wa_lines.append("📁 דשבורד: file:///C:/Users/user/porto-pessoa/dashboard/out/index.html")
    wa_text = "\n".join(wa_lines)

    rows_html = "".join(
        f"<tr><td>{i}.</td><td><b>{r['typology']} {r['freguesia']}</b><br>"
        f"<small>{(r['address'] or '')[:60]}</small></td>"
        f"<td>{r['area_m2']}m²</td><td>€{r['price_eur']:,}</td>"
        f"<td><b>{r['composite']:.1f}</b>/10</td></tr>"
        for i, r in enumerate(top, 1)
    ) or '<tr><td colspan="5"><i>אין נכסים חדשים מעל הסף השבוע</i></td></tr>'

    gmail_html = f"""
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 680px; margin: 0 auto;">
      <h2 style="color: #3a7fc1;">🏛️ PESSOA · פורטו מרכז · {date_str}</h2>
      <p><b>{new_count}</b> נכסים חדשים השבוע · <b>{len(top)}</b> עברו סף {NOTIFY_THRESHOLD_COMPOSITE}</p>
      <h3>הטופ 5 השבועי</h3>
      <table border="0" cellspacing="0" cellpadding="8" style="width:100%; border-collapse: collapse; border: 1px solid #ddd;">
        <thead style="background: #f4ede0;">
          <tr><th>#</th><th>נכס</th><th>שטח</th><th>מחיר</th><th>ציון</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="margin-top: 20px; color: #666; font-size: 13px;">
        דוח מלא בדשבורד: <br>
        <code>file:///C:/Users/user/porto-pessoa/dashboard/out/index.html</code>
      </p>
      <p style="color: #999; font-size: 11px; margin-top: 30px;">
        PESSOA Suite · FAROL Scanner + 5 Sub-Agents · Build local · {datetime.now().isoformat(timespec='minutes')}
      </p>
    </div>
    """
    return {
        "text": wa_text,
        "html": gmail_html,
        "subject": f"PESSOA · פורטו מרכז · {len(top)} נכסים חדשים מעל סף · {date_str}",
        "new_count": new_count,
        "top_count": len(top),
    }


if __name__ == "__main__":
    s = build()
    print(s["text"])
