"""Dashboard generator — list view + per-property drill-down.

Tabs:
- 'all'       — every property, paginated 30/page, sortable, filterable by typology.
- 'composite' — top 30 by PESSOA composite (scored only).
- 'score_a..e' — top 30 by each sub-agent.

All pages are static HTML; sort/filter/pagination are client-side JS.
"""
import html
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, DASH_OUT, FREGUESIAS

DASH_OUT.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = Path(__file__).parent / "assets"

SOURCE_LABELS = {
    "idealista": "Idealista", "imovirtual": "Imovirtual",
    "casa_sapo": "Casa Sapo", "supercasa": "Supercasa",
    "custojusto": "Custojusto",
}
SOURCE_URL_PREFIX = {
    "idealista": "Idealista",  "imovirtual": "Imov.",
    "casa_sapo": "Sapo", "supercasa": "SuperC.", "custojusto": "CJ",
}


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _all_properties() -> list[dict]:
    with _conn() as db:
        rows = db.execute("SELECT * FROM v_top_properties ORDER BY id DESC").fetchall()
        listings_by_prop = {}
        for r in db.execute("SELECT property_id, source, url, asking_price FROM listings"):
            listings_by_prop.setdefault(r["property_id"], []).append(dict(r))
    out = []
    for r in rows:
        d = dict(r)
        d["listings"] = listings_by_prop.get(d["id"], [])
        out.append(d)
    return out


def _top_by_score(column: str, limit: int = 30) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            f"SELECT * FROM v_top_properties WHERE {column} IS NOT NULL ORDER BY {column} DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def _scan_meta() -> dict:
    with _conn() as db:
        last = db.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
        total = db.execute("SELECT COUNT(*) c FROM properties WHERE status='active'").fetchone()["c"]
        scored = db.execute("SELECT COUNT(DISTINCT property_id) c FROM scores").fetchone()["c"]
        by_typ = {r["t"]: r["c"] for r in db.execute(
            "SELECT typology t, COUNT(*) c FROM properties WHERE status='active' AND typology IS NOT NULL GROUP BY t"
        )}
    return {
        "last_scan": dict(last) if last else {},
        "total": total, "scored": scored, "by_typology": by_typ,
    }


def _row_data(p: dict) -> dict:
    """Serialize one property for JSON embedding in HTML (JS consumes this)."""
    listings = p.get("listings", [])
    sources = [{"source": l["source"], "url": l["url"]} for l in listings]
    return {
        "id": p["id"],
        "typology": p["typology"] or "",
        "freguesia": p["freguesia"] or "",
        "address": (p["address"] or "")[:120],
        "area_m2": p["area_m2"] or 0,
        "price_eur": p["price_eur"] or 0,
        "price_per_m2": round(p["price_per_m2"] or 0, 0),
        "built_year": p["built_year"] or 0,
        "energy_cert": p["energy_cert"] or "",
        "score_a": p.get("score_a"),
        "score_b": p.get("score_b"),
        "score_c": p.get("score_c"),
        "score_d": p.get("score_d"),
        "score_e": p.get("score_e"),
        "composite": p.get("composite"),
        "verdict": p.get("verdict") or "",
        "sources": sources,
        "source_count": len(sources),
        "url_first": listings[0]["url"] if listings else "",
    }


def _render_index(all_props: list[dict], by_score: dict[str, list[dict]], meta: dict) -> str:
    all_data = [_row_data(p) for p in all_props]
    score_data = {k: [_row_data(p) for p in v] for k, v in by_score.items()}

    last_scan = meta["last_scan"].get("finished_at", "—")
    typ_counts = meta["by_typology"]
    typ_pills = " ".join(
        f'<button class="pill" data-typ="{t}">{t} <small>{typ_counts.get(t, 0)}</small></button>'
        for t in ["T0", "T1", "T2", "T3"]
    )
    score_pills = (
        '<button class="pill score-pill" data-score="any">עם ציון <small>' + str(meta["scored"]) + '</small></button>'
        '<button class="pill score-pill" data-score="none">ללא ציון <small>' + str(meta["total"] - meta["scored"]) + '</small></button>'
    )

    # Embed JSON datasets in <script> for client-side rendering
    data_json = json.dumps({
        "all": all_data,
        "composite": score_data.get("composite", []),
        "score_a": score_data.get("score_a", []),
        "score_b": score_data.get("score_b", []),
        "score_c": score_data.get("score_c", []),
        "score_d": score_data.get("score_d", []),
        "score_e": score_data.get("score_e", []),
    }, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PESSOA · פורטו מרכז · דשבורד</title>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500;700;900&family=Heebo:wght@300;400;500;700;800&family=Fraunces:ital,wght@0,400..700;1,400..700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-0:#080c18;--bg-1:#0e1424;--bg-2:#141b32;--line:#2a3560;--line-soft:#1d2648;
  --text-0:#f4ede0;--text-1:#c8c2b2;--text-2:#7e8399;--text-3:#545971;
  --accent-azulejo:#3a7fc1;--accent-gold:#e4b864;--accent-gold-b:#f0ce84;
  --agent-a:#5cc69a;--agent-b:#e09a5f;--agent-c:#e2525f;--agent-d:#5ba0e3;--agent-e:#b593e0;
  --serif-he:"Frank Ruhl Libre",serif;--serif-en:"Fraunces",serif;
  --sans:"Heebo",sans-serif;--mono:"JetBrains Mono",monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--sans);background:var(--bg-0);color:var(--text-0);min-height:100vh;line-height:1.6;font-size:15px;
  background-image:radial-gradient(ellipse 1000px 500px at 80% 0%,rgba(58,127,193,.08),transparent 70%),
    radial-gradient(ellipse 800px 400px at 0% 20%,rgba(228,184,100,.05),transparent 70%),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60'%3E%3Cg fill='%231a2344' fill-opacity='.18'%3E%3Cpath d='M30 0L40 20L60 30L40 40L30 60L20 40L0 30L20 20Z'/%3E%3C/g%3E%3C/svg%3E");
  background-attachment:fixed}}
.container{{max-width:1480px;margin:0 auto;padding:0 32px}}
header.top{{border-bottom:1px solid var(--line-soft);padding:20px 0;margin-bottom:36px;position:sticky;top:0;z-index:10;background:rgba(8,12,24,.85);backdrop-filter:blur(10px)}}
.top-inner{{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:14px}}
.brand-mark{{width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,var(--accent-azulejo),var(--accent-gold));display:grid;place-items:center;font-family:var(--serif-en);font-weight:700;font-size:22px;color:var(--bg-0)}}
.brand-name{{font-family:var(--serif-he);font-weight:700;font-size:19px}}
.brand-sub{{font-size:11px;letter-spacing:1.5px;color:var(--text-2);margin-top:2px}}
.meta{{display:flex;gap:20px;font-size:12px;color:var(--text-2);align-items:center}}
.meta strong{{color:var(--text-0);margin-inline-start:6px}}
.calc-btn{{display:flex;align-items:center;gap:10px;padding:8px 14px;border-radius:10px;
  background:linear-gradient(135deg,rgba(228,184,100,.18),rgba(228,184,100,.06));
  border:1px solid rgba(228,184,100,.4);text-decoration:none;color:var(--accent-gold-b);
  transition:all .2s;cursor:pointer}}
.calc-btn:hover{{background:linear-gradient(135deg,rgba(228,184,100,.32),rgba(228,184,100,.14));
  border-color:var(--accent-gold);transform:translateY(-1px);box-shadow:0 6px 20px -8px rgba(228,184,100,.5)}}
.calc-icon{{font-family:var(--serif-en);font-size:22px;font-weight:700;line-height:1;
  width:32px;height:32px;display:grid;place-items:center;border-radius:8px;
  background:linear-gradient(135deg,var(--accent-azulejo),var(--accent-gold));color:var(--bg-0)}}
.calc-label{{display:flex;flex-direction:column;gap:1px;line-height:1.15}}
.calc-label strong{{font-family:var(--serif-he);font-size:14px;font-weight:700;color:var(--accent-gold-b);margin:0}}
.calc-label small{{font-family:var(--serif-en);font-style:italic;font-size:10px;color:var(--text-2);letter-spacing:.5px}}
h1.dash{{font-family:var(--serif-he);font-size:46px;font-weight:700;letter-spacing:-1px;margin-bottom:10px}}
h1.dash em{{font-style:italic;color:var(--accent-gold-b);font-weight:400}}
.lede{{color:var(--text-1);font-size:15px;max-width:860px;margin-bottom:28px}}
.stats-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line-soft);border-radius:14px;overflow:hidden;border:1px solid var(--line-soft);margin-bottom:28px}}
.stat{{background:var(--bg-1);padding:16px 22px}}
.stat .k{{font-size:10px;letter-spacing:1px;color:var(--text-2);font-weight:700;text-transform:uppercase}}
.stat .v{{font-family:var(--serif-he);font-size:26px;font-weight:700;color:var(--text-0);margin-top:6px}}

.tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}}
.tab-btn{{background:var(--bg-1);border:1px solid var(--line-soft);color:var(--text-1);padding:9px 18px;border-radius:10px;font-family:var(--sans);font-size:13px;font-weight:700;cursor:pointer;display:flex;flex-direction:column;gap:1px;align-items:flex-start;transition:border-color .15s,background .15s}}
.tab-btn small{{font-family:var(--serif-en);font-style:italic;font-size:10px;color:var(--text-2);font-weight:400}}
.tab-btn:hover{{border-color:var(--line)}}
.tab-btn.active{{background:var(--bg-2);border-color:var(--accent-gold);color:var(--accent-gold-b)}}
.tab-btn.active small{{color:var(--text-1)}}

.filters{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;padding:14px 18px;background:var(--bg-1);border:1px solid var(--line-soft);border-radius:10px;align-items:center}}
.filters label{{font-size:12px;color:var(--text-2);font-weight:700;letter-spacing:.5px;margin-inline-end:4px}}
.pill{{background:transparent;border:1px solid var(--line);color:var(--text-1);padding:5px 12px;border-radius:8px;font-family:var(--sans);font-size:12px;font-weight:700;cursor:pointer;transition:all .15s}}
.pill small{{font-family:var(--mono);color:var(--text-3);font-weight:400;margin-inline-start:4px}}
.pill:hover{{border-color:var(--accent-gold)}}
.pill.active{{background:var(--accent-gold);color:var(--bg-0);border-color:var(--accent-gold)}}
.pill.active small{{color:var(--bg-0);opacity:.7}}
.range-filter{{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--text-2)}}
.range-filter input{{width:90px;background:var(--bg-2);border:1px solid var(--line);color:var(--text-0);padding:4px 8px;border-radius:6px;font-family:var(--mono);font-size:12px;direction:ltr;text-align:right}}

.panel{{background:var(--bg-1);border:1px solid var(--line-soft);border-radius:14px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
thead th{{font-size:11px;letter-spacing:1px;color:var(--text-2);font-weight:700;text-align:right;padding:12px 14px;background:var(--bg-2);border-bottom:1px solid var(--line-soft);cursor:pointer;user-select:none;white-space:nowrap}}
thead th:hover{{color:var(--accent-gold-b)}}
thead th.sort-asc::after{{content:" ▲";color:var(--accent-gold);font-size:9px}}
thead th.sort-desc::after{{content:" ▼";color:var(--accent-gold);font-size:9px}}
tbody tr{{border-bottom:1px solid var(--line-soft);cursor:pointer;transition:background .1s}}
tbody tr:hover{{background:rgba(228,184,100,.04)}}
tbody td{{padding:12px 14px;vertical-align:middle}}
td.rank{{font-family:var(--mono);color:var(--text-3);font-size:12px;width:40px}}
td.addr{{font-size:13px;max-width:280px}}
td.addr strong{{font-family:var(--serif-he);font-size:14px;display:block}}
.addr-sub{{color:var(--text-2);font-size:11px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
td.num{{font-family:var(--mono);font-size:13px;color:var(--text-0);direction:ltr;text-align:right;white-space:nowrap}}
td.num small{{color:var(--text-3);font-size:10px}}
.score-pill-cell{{font-family:var(--mono);font-weight:700;font-size:15px;padding:4px 10px;border-radius:6px;background:linear-gradient(135deg,rgba(228,184,100,.14),rgba(228,184,100,.04));border:1px solid rgba(228,184,100,.3);color:var(--accent-gold-b);display:inline-block;direction:ltr;text-decoration:none;transition:all .15s}}
a.score-pill-cell:hover{{background:linear-gradient(135deg,rgba(228,184,100,.28),rgba(228,184,100,.1));border-color:var(--accent-gold)}}
.score-na{{color:var(--text-3);font-size:12px;font-style:italic}}
.dim-strip{{direction:ltr;text-align:right;white-space:nowrap}}
.dim{{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;margin-right:2px}}
.dim.a{{background:rgba(92,198,154,.12);color:var(--agent-a)}}.dim.b{{background:rgba(224,154,95,.12);color:var(--agent-b)}}.dim.c{{background:rgba(226,82,95,.12);color:var(--agent-c)}}.dim.d{{background:rgba(91,160,227,.12);color:var(--agent-d)}}.dim.e{{background:rgba(181,147,224,.12);color:var(--agent-e)}}
.src-count{{font-family:var(--mono);font-size:11px;color:var(--text-2);direction:ltr}}
.src-badges{{display:inline-flex;gap:2px;flex-wrap:wrap}}
.src-badge{{display:inline-block;background:var(--bg-2);border:1px solid var(--line);padding:2px 7px;border-radius:4px;font-family:var(--mono);font-size:10px;font-weight:700;color:var(--text-1);letter-spacing:.3px;text-decoration:none;transition:all .15s;cursor:pointer}}
a.src-badge:hover{{background:var(--accent-azulejo);color:var(--bg-0);border-color:var(--accent-azulejo)}}
.empty{{text-align:center;padding:40px;color:var(--text-3);font-style:italic}}
.pager{{display:flex;justify-content:center;gap:6px;padding:18px;border-top:1px solid var(--line-soft);background:var(--bg-2)}}
.pager button{{background:transparent;border:1px solid var(--line);color:var(--text-1);padding:6px 12px;border-radius:6px;font-family:var(--mono);font-size:12px;cursor:pointer}}
.pager button.active{{background:var(--accent-gold);color:var(--bg-0);border-color:var(--accent-gold)}}
.pager button:disabled{{opacity:.3;cursor:not-allowed}}
.pager .info{{color:var(--text-2);font-size:12px;padding:6px 10px}}
footer.bot{{border-top:1px solid var(--line-soft);padding:28px 0;margin-top:50px;text-align:center;font-size:11px;color:var(--text-3);font-family:var(--mono);letter-spacing:1.5px}}
footer.bot span{{color:var(--accent-azulejo)}}
</style>
</head>
<body>
<header class="top">
  <div class="container top-inner">
    <div class="brand">
      <div class="brand-mark">P</div>
      <div><div class="brand-name">PESSOA · פורטו מרכז</div><div class="brand-sub">FAROL Scanner + PESSOA Deep · On-demand</div></div>
    </div>
    <div class="meta">
      <a class="calc-btn" href="investment-calculator.html" target="_blank" title="מחשבון השקעה · Investment Calculator">
        <span class="calc-icon">₪</span>
        <div class="calc-label">
          <strong>מחשבון השקעה</strong>
          <small>Investment Calculator</small>
        </div>
      </a>
      <span>סריקה אחרונה <strong>{html.escape(last_scan)}</strong></span>
      <span>ב-DB <strong>{meta['total']}</strong></span>
      <span>נותחו <strong>{meta['scored']}</strong></span>
    </div>
  </div>
</header>
<main class="container">
  <h1 class="dash">כל הנכסים <em>בפורטו מרכז</em></h1>
  <p class="lede">סרוקים מ-5 לוחות פורטוגלים. מיין לפי כל עמודה בלחיצה על כותרת. סנן לפי טיפולוגיה, מחיר, או סטטוס ניתוח.</p>
  <div class="stats-row">
    <div class="stat"><div class="k">סך נכסים</div><div class="v">{meta['total']}</div></div>
    <div class="stat"><div class="k">נותחו בעומק</div><div class="v">{meta['scored']}</div></div>
    <div class="stat"><div class="k">מקורות פעילים</div><div class="v">{len([k for k in SOURCE_LABELS if k])}</div></div>
    <div class="stat"><div class="k">Freguesias</div><div class="v">{len(FREGUESIAS)}</div></div>
  </div>

  <div class="tabs">
    <button class="tab-btn active" data-tab="all">כל הנכסים <small>All · {meta['total']}</small></button>
    <button class="tab-btn" data-tab="composite">ציון מצרפי <small>Composite</small></button>
    <button class="tab-btn" data-tab="score_a">A · פיננסי <small>Financial</small></button>
    <button class="tab-btn" data-tab="score_b">B · מבנה <small>Structural</small></button>
    <button class="tab-btn" data-tab="score_c">C · חוק <small>Legal</small></button>
    <button class="tab-btn" data-tab="score_d">D · מיקום <small>Location</small></button>
    <button class="tab-btn" data-tab="score_e">E · סיכון <small>Risk</small></button>
  </div>

  <div class="filters" id="filters-bar">
    <label>טיפולוגיה:</label>
    <button class="pill active" data-typ="all">הכל <small>{meta['total']}</small></button>
    {typ_pills}
    <label style="margin-inline-start:16px">ניתוח:</label>
    <button class="pill active" data-score="all">הכל</button>
    {score_pills}
    <div class="range-filter" style="margin-inline-start:16px">
      <label>מחיר €</label>
      <input type="number" id="price-min" placeholder="מינ׳" step="10000">
      <span>–</span>
      <input type="number" id="price-max" placeholder="מקס׳" step="10000">
    </div>
    <div class="range-filter">
      <label>שטח m²</label>
      <input type="number" id="area-min" placeholder="מינ׳" step="5">
      <span>–</span>
      <input type="number" id="area-max" placeholder="מקס׳" step="5">
    </div>
  </div>

  <div class="panel">
    <table id="maintable">
      <thead>
        <tr>
          <th>#</th>
          <th data-sort="typology">טיפולוגיה</th>
          <th data-sort="freguesia">פריגזיה</th>
          <th data-sort="address">כתובת</th>
          <th data-sort="area_m2">שטח</th>
          <th data-sort="price_eur">מחיר</th>
          <th data-sort="price_per_m2">€/m²</th>
          <th data-sort="composite">ציון</th>
          <th>A·B·C·D·E</th>
          <th data-sort="source_count">לוחות</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="pager" id="pager"></div>
  </div>
</main>
<footer class="bot"><div class="container"><span>PESSOA Suite</span> · FAROL Scanner + PESSOA Deep · {datetime.now().strftime('%Y-%m-%d %H:%M')}</div></footer>

<script>
const DATA = {data_json};
const SRC_LABEL = {json.dumps(SOURCE_URL_PREFIX)};

const state = {{
  tab: 'all',
  typ: 'all',
  score: 'all',
  priceMin: null, priceMax: null, areaMin: null, areaMax: null,
  sortKey: null, sortDir: 'desc',
  page: 1, perPage: 30,
}};

function getBase() {{
  return DATA[state.tab] || DATA.all;
}}

function filter(rows) {{
  return rows.filter(r => {{
    if (state.typ !== 'all' && r.typology !== state.typ) return false;
    if (state.score === 'any' && r.composite == null) return false;
    if (state.score === 'none' && r.composite != null) return false;
    if (state.priceMin != null && r.price_eur < state.priceMin) return false;
    if (state.priceMax != null && r.price_eur > state.priceMax) return false;
    if (state.areaMin != null && r.area_m2 < state.areaMin) return false;
    if (state.areaMax != null && r.area_m2 > state.areaMax) return false;
    return true;
  }});
}}

function sortRows(rows) {{
  if (!state.sortKey) return rows;
  const k = state.sortKey;
  const dir = state.sortDir === 'desc' ? -1 : 1;
  return rows.slice().sort((a, b) => {{
    const av = a[k] ?? -Infinity, bv = b[k] ?? -Infinity;
    if (typeof av === 'string') return av.localeCompare(bv) * dir;
    return (av - bv) * dir;
  }});
}}

function rowHtml(r, idx) {{
  const dims = r.score_a != null
    ? `<span class="dim a">${{r.score_a.toFixed(1)}}</span><span class="dim b">${{r.score_b.toFixed(1)}}</span><span class="dim c">${{r.score_c.toFixed(1)}}</span><span class="dim d">${{r.score_d.toFixed(1)}}</span><span class="dim e">${{r.score_e.toFixed(1)}}</span>`
    : '<span class="score-na">—</span>';
  const composite = r.composite != null
    ? `<span class="score-pill-cell">${{r.composite.toFixed(1)}}</span>`
    : '<span class="score-na">לא נותח</span>';
  const badges = (r.sources || []).map(s => `<a class="src-badge" href="${{s.url}}" target="_blank" onclick="event.stopPropagation()" title="${{s.source}}">${{SRC_LABEL[s.source]||s.source}}</a>`).join('');
  const compositeCell = r.composite != null
    ? `<a class="score-pill-cell" href="property_${{r.id}}.html" onclick="event.stopPropagation()">${{r.composite.toFixed(1)}}</a>`
    : '<span class="score-na">לא נותח</span>';
  const rowUrl = r.url_first || '#';
  return `
    <tr onclick="window.open('${{rowUrl}}', '_blank')" title="פתח בלוח המקור">
      <td class="rank">#${{idx}}</td>
      <td><strong>${{r.typology||'—'}}</strong></td>
      <td>${{r.freguesia||'<span class="score-na">—</span>'}}</td>
      <td class="addr"><span class="addr-sub">${{escape(r.address||'—')}}</span></td>
      <td class="num">${{r.area_m2||'—'}}<small> m²</small></td>
      <td class="num">€${{(r.price_eur||0).toLocaleString()}}</td>
      <td class="num">€${{(r.price_per_m2||0).toLocaleString()}}<small>/m²</small></td>
      <td>${{compositeCell}}</td>
      <td class="dim-strip">${{dims}}</td>
      <td><span class="src-badges">${{badges}}</span> <span class="src-count">${{r.source_count}}/5</span></td>
    </tr>
  `;
}}

function escape(s) {{ return (s||'').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]); }}

function render() {{
  const base = getBase();
  const filtered = filter(base);
  const sorted = sortRows(filtered);
  const totalPages = Math.max(1, Math.ceil(sorted.length / state.perPage));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * state.perPage;
  const slice = sorted.slice(start, start + state.perPage);

  const tbody = document.getElementById('tbody');
  tbody.innerHTML = slice.length
    ? slice.map((r, i) => rowHtml(r, start + i + 1)).join('')
    : '<tr><td colspan="10" class="empty">אין תוצאות לפילטרים האלה</td></tr>';

  // Pager
  const pager = document.getElementById('pager');
  let html = `<span class="info">${{filtered.length}} תוצאות · עמוד ${{state.page}} מתוך ${{totalPages}}</span>`;
  html += `<button onclick="setPage(${{state.page-1}})" ${{state.page<=1?'disabled':''}}>→</button>`;
  for (let i = Math.max(1, state.page-2); i <= Math.min(totalPages, state.page+2); i++) {{
    html += `<button onclick="setPage(${{i}})" class="${{i===state.page?'active':''}}">${{i}}</button>`;
  }}
  html += `<button onclick="setPage(${{state.page+1}})" ${{state.page>=totalPages?'disabled':''}}>←</button>`;
  pager.innerHTML = html;

  // Update sort indicators on headers
  document.querySelectorAll('thead th').forEach(th => {{
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.sort === state.sortKey) th.classList.add('sort-' + state.sortDir);
  }});
}}

function setPage(p) {{ state.page = p; render(); }}

// Sort handlers
document.querySelectorAll('thead th[data-sort]').forEach(th => {{
  th.onclick = () => {{
    const k = th.dataset.sort;
    if (state.sortKey === k) state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
    else {{ state.sortKey = k; state.sortDir = 'desc'; }}
    state.page = 1;
    render();
  }};
}});

// Tab handlers
document.querySelectorAll('.tab-btn').forEach(b => {{
  b.onclick = () => {{
    document.querySelectorAll('.tab-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    state.tab = b.dataset.tab;
    state.page = 1;
    state.sortKey = state.tab === 'all' ? null : state.tab;
    state.sortDir = 'desc';
    render();
  }};
}});

// Typology pills
document.querySelectorAll('[data-typ]').forEach(p => {{
  p.onclick = () => {{
    document.querySelectorAll('[data-typ]').forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    state.typ = p.dataset.typ;
    state.page = 1;
    render();
  }};
}});

// Score-status pills
document.querySelectorAll('[data-score]').forEach(p => {{
  p.onclick = () => {{
    document.querySelectorAll('[data-score]').forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    state.score = p.dataset.score;
    state.page = 1;
    render();
  }};
}});

// Range inputs
['price-min','price-max','area-min','area-max'].forEach(id => {{
  document.getElementById(id).addEventListener('input', e => {{
    const key = id.replace('-','').replace('min','Min').replace('max','Max');
    state[key] = e.target.value === '' ? null : +e.target.value;
    state.page = 1;
    render();
  }});
}});

render();
</script>
</body>
</html>"""


def _render_property_page(pid: int) -> str:
    """Single-property drill-down (unchanged from prior version)."""
    with _conn() as db:
        p = db.execute("SELECT * FROM v_top_properties WHERE id=?", (pid,)).fetchone()
        s = db.execute("SELECT * FROM v_latest_scores WHERE property_id=?", (pid,)).fetchone()
        listings = db.execute("SELECT * FROM listings WHERE property_id=?", (pid,)).fetchall()
    if not p:
        return "<h1>נכס לא נמצא</h1>"

    sources_section = "\n".join(
        f'<a class="src-link" href="{html.escape(l["url"])}" target="_blank">'
        f'<strong>{SOURCE_LABELS.get(l["source"], l["source"])}</strong>'
        f'<span>€{(l["asking_price"] or 0):,}</span></a>'
        for l in listings
    )
    composite = p["composite"] or 0
    verdict_map = {"strong_buy": "קנייה חזקה", "buy": "קנייה", "hold": "המתן",
                   "pass": "וותר", "strong_pass": "וותר חד"}
    verdict_he = verdict_map.get(p["verdict"], "לא נותח")
    verdict_cls = p["verdict"] or "hold"

    def bullets_html(text: str) -> str:
        if not text:
            return "<li class='empty'>אין נתונים</li>"
        lines = [l.strip("-• ").strip() for l in text.splitlines() if l.strip()]
        return "\n".join(f"<li>{html.escape(l)}</li>" for l in lines)

    return f"""<!doctype html>
<html lang="he" dir="rtl"><head><meta charset="UTF-8">
<title>PESSOA · {html.escape((p['typology'] or '') + ' ' + (p['freguesia'] or ''))}</title>
<link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@400;500;700;900&family=Heebo:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--bg-0:#080c18;--bg-1:#0e1424;--bg-2:#141b32;--line:#2a3560;--line-soft:#1d2648;--text-0:#f4ede0;--text-1:#c8c2b2;--text-2:#7e8399;--text-3:#545971;--accent-gold:#e4b864;--accent-gold-b:#f0ce84;--accent-azulejo:#3a7fc1;--agent-a:#5cc69a;--agent-b:#e09a5f;--agent-c:#e2525f;--agent-d:#5ba0e3;--agent-e:#b593e0;--success:#5cc69a;--danger:#ef4b5c}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:"Heebo",sans-serif;background:var(--bg-0);color:var(--text-0);line-height:1.6;min-height:100vh}}
.container{{max-width:1240px;margin:0 auto;padding:32px}}.back{{color:var(--text-2);font-size:13px;text-decoration:none;margin-bottom:20px;display:inline-block}}.back:hover{{color:var(--accent-gold-b)}}
h1{{font-family:"Frank Ruhl Libre",serif;font-size:44px;font-weight:700;margin:10px 0}}.loc{{color:var(--text-1);font-size:15px;margin-bottom:28px}}
.verdict{{display:inline-block;font-family:"Frank Ruhl Libre";font-size:30px;font-weight:700;padding:6px 22px;border-radius:10px;background:linear-gradient(135deg,rgba(228,184,100,.14),rgba(228,184,100,.04));border:1px solid rgba(228,184,100,.3);color:var(--accent-gold-b);margin-bottom:10px}}
.verdict.buy,.verdict.strong_buy{{color:var(--success);background:linear-gradient(135deg,rgba(92,198,154,.14),rgba(92,198,154,.04));border-color:rgba(92,198,154,.3)}}
.verdict.pass,.verdict.strong_pass{{color:var(--danger);background:linear-gradient(135deg,rgba(239,75,92,.14),rgba(239,75,92,.04));border-color:rgba(239,75,92,.3)}}
.composite{{font-family:"JetBrains Mono";font-size:17px;color:var(--text-1);margin-bottom:28px;direction:ltr;text-align:right}}.composite strong{{color:var(--accent-gold-b);font-size:30px;font-family:"Frank Ruhl Libre"}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line-soft);border-radius:14px;overflow:hidden;border:1px solid var(--line-soft);margin-bottom:30px}}
.stat{{background:var(--bg-1);padding:16px 20px}}.stat .k{{font-size:10px;letter-spacing:1px;color:var(--text-2);font-weight:700}}.stat .v{{font-family:"Frank Ruhl Libre";font-size:22px;font-weight:700;color:var(--text-0);margin-top:6px}}
section.block{{margin-bottom:36px}}h2{{font-family:"Frank Ruhl Libre";font-size:24px;font-weight:700;padding-bottom:12px;margin-bottom:18px;border-bottom:1px solid var(--line-soft)}}
.agents{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.agent{{background:var(--bg-1);border:1px solid var(--line-soft);border-radius:12px;padding:20px;position:relative}}
.agent::before{{content:"";position:absolute;right:0;top:22px;bottom:22px;width:3px;border-radius:3px 0 0 3px}}
.agent.a::before{{background:var(--agent-a)}}.agent.b::before{{background:var(--agent-b)}}.agent.c::before{{background:var(--agent-c)}}.agent.d::before{{background:var(--agent-d)}}.agent.e::before{{background:var(--agent-e)}}
.agent-head{{display:flex;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid var(--line-soft);margin-bottom:12px}}
.agent-title{{font-family:"Frank Ruhl Libre";font-size:18px;font-weight:700}}.agent-title small{{display:block;font-size:10px;letter-spacing:1.5px;color:var(--text-2);font-weight:700;margin-bottom:2px}}
.agent.a .agent-title small{{color:var(--agent-a)}}.agent.b .agent-title small{{color:var(--agent-b)}}.agent.c .agent-title small{{color:var(--agent-c)}}.agent.d .agent-title small{{color:var(--agent-d)}}.agent.e .agent-title small{{color:var(--agent-e)}}
.agent-score{{font-family:"JetBrains Mono";font-size:19px;font-weight:500;direction:ltr}}
.agent ul{{list-style:none}}.agent li{{padding:5px 0;color:var(--text-1);font-size:13px;display:grid;grid-template-columns:14px 1fr;gap:8px}}.agent li::before{{content:"—";color:var(--text-3)}}.agent li.empty{{color:var(--text-3);font-style:italic}}
.sources-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}}
.src-link{{display:flex;flex-direction:column;gap:4px;padding:12px 16px;background:var(--bg-1);border:1px solid var(--line-soft);border-radius:10px;text-decoration:none;color:var(--text-0);transition:border-color .2s}}
.src-link:hover{{border-color:var(--accent-azulejo)}}.src-link strong{{font-family:"Frank Ruhl Libre";font-size:15px}}.src-link span{{color:var(--text-2);font-family:"JetBrains Mono";font-size:12px;direction:ltr}}
</style></head><body><div class="container">
<a class="back" href="index.html">← חזרה לרשימה</a>
<h1>{html.escape((p['typology'] or '') + ' ' + (p['freguesia'] or ''))} · {p['area_m2']} מ"ר</h1>
<div class="loc">{html.escape(p['address'] or '')}</div>
<div class="verdict {verdict_cls}">{verdict_he}</div>
<div class="composite">ציון מצרפי <strong>{composite:.1f}</strong>/10 · {p['scored_at'] or '—'}</div>
<div class="grid">
  <div class="stat"><div class="k">מחיר</div><div class="v">€{(p['price_eur'] or 0):,}</div></div>
  <div class="stat"><div class="k">€/מ"ר</div><div class="v">€{(p['price_per_m2'] or 0):,.0f}</div></div>
  <div class="stat"><div class="k">שטח</div><div class="v">{p['area_m2'] or '—'} m²</div></div>
  <div class="stat"><div class="k">טיפולוגיה</div><div class="v">{p['typology'] or '—'}</div></div>
</div>
<section class="block"><h2>ממצאי 5 סוכני משנה</h2><div class="agents">
<div class="agent a"><div class="agent-head"><div class="agent-title"><small>Sub-Agent A</small>פיננסי</div><div class="agent-score">{(p['score_a'] or 0):.1f}/10</div></div><ul>{bullets_html(s['agent_a_json'] if s else '')}</ul></div>
<div class="agent b"><div class="agent-head"><div class="agent-title"><small>Sub-Agent B</small>מבנה</div><div class="agent-score">{(p['score_b'] or 0):.1f}/10</div></div><ul>{bullets_html(s['agent_b_json'] if s else '')}</ul></div>
<div class="agent c"><div class="agent-head"><div class="agent-title"><small>Sub-Agent C · Critical</small>משפטי</div><div class="agent-score">{(p['score_c'] or 0):.1f}/10</div></div><ul>{bullets_html(s['agent_c_json'] if s else '')}</ul></div>
<div class="agent d"><div class="agent-head"><div class="agent-title"><small>Sub-Agent D</small>מיקום</div><div class="agent-score">{(p['score_d'] or 0):.1f}/10</div></div><ul>{bullets_html(s['agent_d_json'] if s else '')}</ul></div>
<div class="agent e"><div class="agent-head"><div class="agent-title"><small>Sub-Agent E</small>סיכון</div><div class="agent-score">{(p['score_e'] or 0):.1f}/10</div></div><ul>{bullets_html(s['agent_e_json'] if s else '')}</ul></div>
</div></section>
<section class="block"><h2>זמין בלוחות</h2><div class="sources-grid">{sources_section}</div></section>
</div></body></html>"""


def _copy_assets():
    """Copy static assets (e.g. investment calculator) from assets/ to out/."""
    if not ASSETS_DIR.exists():
        return
    for asset in ASSETS_DIR.iterdir():
        if asset.is_file():
            shutil.copy2(asset, DASH_OUT / asset.name)


def build():
    _copy_assets()
    meta = _scan_meta()
    all_props = _all_properties()
    by_score = {
        "composite": _top_by_score("composite"),
        "score_a":   _top_by_score("score_a"),
        "score_b":   _top_by_score("score_b"),
        "score_c":   _top_by_score("score_c"),
        "score_d":   _top_by_score("score_d"),
        "score_e":   _top_by_score("score_e"),
    }
    (DASH_OUT / "index.html").write_text(_render_index(all_props, by_score, meta), encoding="utf-8")

    # Per-property drill-down — only scored ones (unscored go to external URL in JS)
    with _conn() as db:
        scored_ids = [r["property_id"] for r in db.execute("SELECT DISTINCT property_id FROM scores")]
    for pid in scored_ids:
        (DASH_OUT / f"property_{pid}.html").write_text(_render_property_page(pid), encoding="utf-8")

    print(f"[dashboard] {meta['total']} properties · {len(scored_ids)} scored drill-downs")


if __name__ == "__main__":
    build()
