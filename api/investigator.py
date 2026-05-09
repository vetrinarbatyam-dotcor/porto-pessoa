"""PESSOA Full Investigation — Opus-level deep property analysis."""
import sqlite3, subprocess, json, re, requests, sys, os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, FREGUESIA_PROFILE, FREGUESIA_MEDIANS_EUR_PER_M2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

AL_ZONE_STATUS = {
    "Ribeira":         "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Sé":              "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Miragaia":        "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Baixa":           "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Santo Ildefonso": "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Vitória":         "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "São Nicolau":     "🔴 FROZEN — AL moratorium Dec 2024, novos registos suspensos indefinidamente",
    "Cedofeita":       "🟡 RESTRICTED — zona de contenção, novos registos possíveis mas sob escrutínio",
    "Bonfim":          "🟡 RESTRICTED — liberalizado 2024 mas sob monitorização; risco de nova contenção",
    "Massarelos":      "🟢 PERMITTED — fora da zona core; AL permitido com registo normal",
    "Boavista":        "🟢 PERMITTED — fora da zona core; AL permitido com registo normal",
    "Campanhã":        "🟢 PERMITTED — zona emergente; AL permitido, menor concorrência",
}

AL_RATES_EUR_NIGHT = {
    "Ribeira": 130, "Sé": 110, "Miragaia": 100, "Baixa": 115,
    "Santo Ildefonso": 105, "Vitória": 110, "São Nicolau": 120,
    "Cedofeita": 95, "Bonfim": 90,
    "Massarelos": 85, "Boavista": 95, "Campanhã": 70,
}

LTR_RATE_PER_M2 = {
    "Ribeira": 22, "Sé": 20, "Miragaia": 18, "Baixa": 21,
    "Santo Ildefonso": 18, "Vitória": 18, "São Nicolau": 20,
    "Cedofeita": 17, "Bonfim": 15,
    "Massarelos": 16, "Boavista": 18, "Campanhã": 12,
}


def _fetch_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.text[:6000]
    except Exception as e:
        return f"[fetch failed: {e}]"


def _ddg_search(query: str) -> str:
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": "1", "no_html": "1"},
            headers=HEADERS, timeout=10,
        )
        data = r.json()
        parts = [data.get("Abstract", "")]
        parts += [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5]]
        return "\n".join(p for p in parts if p)[:1500] or "[no results]"
    except:
        return "[search unavailable]"


def run_investigation(property_id: int, send_email: bool = True) -> str:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        prop = db.execute(
            "SELECT p.*, s.score_a, s.score_b, s.score_c, s.score_d, s.score_e, "
            "s.composite, s.verdict, s.summary_md, s.agent_a_json, s.agent_b_json, "
            "s.agent_c_json, s.agent_d_json, s.agent_e_json "
            "FROM properties p LEFT JOIN scores s ON s.property_id = p.id "
            "WHERE p.id = ?",
            (property_id,),
        ).fetchone()
        listings = db.execute(
            "SELECT source, url, asking_price FROM listings WHERE property_id = ?",
            (property_id,),
        ).fetchall()

    if not prop:
        return "<p>Property not found</p>"

    prop = dict(prop)
    listings = [dict(l) for l in listings]

    freg = prop.get("freguesia") or ""
    area = prop.get("area_m2") or 0
    price = prop.get("price_eur") or 0
    typ = prop.get("typology") or ""
    address = prop.get("address") or ""

    median_m2 = FREGUESIA_MEDIANS_EUR_PER_M2.get(freg, 4500)
    price_m2 = round(price / area, 0) if area > 0 else 0
    vs_median_pct = round((price_m2 - median_m2) / median_m2 * 100, 1) if price_m2 > 0 else 0

    al_rate = AL_RATES_EUR_NIGHT.get(freg, 85)
    ltr_m2_rate = LTR_RATE_PER_M2.get(freg, 14)
    ltr_monthly = round((area or 50) * ltr_m2_rate)

    al_gross_annual = al_rate * 365 * 0.70
    al_net_annual = al_gross_annual * 0.70
    al_yield_pct = round(al_net_annual / price * 100, 2) if price > 0 else 0

    ltr_gross_annual = ltr_monthly * 11
    ltr_net_annual = ltr_gross_annual * 0.80
    ltr_yield_pct = round(ltr_net_annual / price * 100, 2) if price > 0 else 0

    breakeven_days = round(ltr_net_annual / (al_rate * 0.70)) if al_rate > 0 else 0
    breakeven_occ_pct = round(breakeven_days / 365 * 100)

    al_status = AL_ZONE_STATUS.get(freg, "Unknown — verify with CM Porto")
    freg_profile = FREGUESIA_PROFILE.get(freg, "Porto neighborhood")

    primary_url = next((l["url"] for l in listings if l.get("url")), "")
    page_content = ""
    if primary_url and "http" in primary_url:
        page_content = _fetch_url(primary_url)

    addr_clean = address.split(",")[0].strip()[:60]
    search1 = _ddg_search(f"{addr_clean} Porto imóvel comprar")
    search2 = _ddg_search(f"alojamento local {freg} Porto 2024 2025 licença")
    search3 = _ddg_search(f"Porto {freg} neighborhood real estate investment 2025")

    prev_notes = "\n".join(filter(None, [
        f"Agent A: {prop.get('agent_a_json')}" if prop.get('agent_a_json') else "",
        f"Agent B: {prop.get('agent_b_json')}" if prop.get('agent_b_json') else "",
        f"Agent C: {prop.get('agent_c_json')}" if prop.get('agent_c_json') else "",
        f"Agent D: {prop.get('agent_d_json')}" if prop.get('agent_d_json') else "",
        f"Agent E: {prop.get('agent_e_json')}" if prop.get('agent_e_json') else "",
    ])) or "No previous quick-score available"

    prompt = f"""You are PESSOA — Porto's elite real estate investment analyst. Perform the most exhaustive possible property investigation for a hybrid AL (Alojamento Local / short-term rental) + LTR (long-term rental) investment strategy. Think as a team: Portuguese property lawyer + chartered surveyor + investment analyst + urban planner + AL operator.

INVESTMENT CONTEXT: Budget €150k–€650k. Goal: hybrid AL+LTR in Porto centro. Investor: non-resident, needs AL license, will hire property manager.

═══ PROPERTY #{property_id} ═══
Address: {address}
Typology: {typ}  |  Area: {area} m²  |  Price: €{price:,}
Freguesia: {freg}
Sources: {', '.join(set(l['source'] for l in listings))}
URL: {primary_url}
Previous quick composite: {prop.get('composite')} ({prop.get('verdict')})

═══ FINANCIAL ESTIMATES ═══
Price/m²: €{price_m2:,.0f} vs parish median €{median_m2:,} → {'+' if vs_median_pct>=0 else ''}{vs_median_pct}% vs median

AL MODEL (avg nightly €{al_rate} for {freg}):
  Gross/yr @70% occ: €{al_gross_annual:,.0f}
  Net/yr after 30% expenses: €{al_net_annual:,.0f} → yield {al_yield_pct}%

LTR MODEL (€{ltr_m2_rate}/m²/mo):
  Monthly: €{ltr_monthly:,} → Net/yr: €{ltr_net_annual:,.0f} → yield {ltr_yield_pct}%

AL breakeven vs LTR: {breakeven_occ_pct}% occupancy ({breakeven_days} nights/yr)

═══ AL REGULATORY — {freg} ═══
{al_status}

═══ NEIGHBORHOOD ═══
{freg_profile}

═══ LISTING CONTENT ═══
{page_content[:3000] if page_content else '[not fetched]'}

═══ SEARCH: ADDRESS ═══
{search1[:600]}

═══ SEARCH: AL TRENDS {freg} ═══
{search2[:600]}

═══ SEARCH: NEIGHBORHOOD 2025 ═══
{search3[:600]}

═══ PREVIOUS QUICK-SCORE ═══
{prev_notes[:800]}

═══ INVESTIGATION PROTOCOL ═══
Respond ONLY with valid JSON (no preamble, no markdown fences). Structure:

{{
  "property_summary": "3 sentences: what is this property, its key characteristic, and the investment thesis in one phrase",
  "agent_a": {{
    "score": <float 0-10>,
    "title": "Financial Viability",
    "headline": "<most important financial finding in one line>",
    "analysis": [
      "PRICE/M²: detailed positioning — exact €/m² vs median, whether overpriced/fair/bargain and why",
      "AL SCENARIO: realistic nightly rate for this exact address, occupancy estimate, gross/net annual, yield — is {al_yield_pct}% achievable?",
      "LTR SCENARIO: realistic monthly rent for this size/location, yield, tenant profile",
      "HYBRID OPTIMAL SPLIT: best AL/LTR calendar strategy for this property, expected blended yield",
      "10-YEAR MODEL: capital appreciation thesis (bull/base/bear), cumulative rental income, total IRR estimate",
      "ACQUISITION COSTS: IMT bracket, notary/registry fees (~1.5%), lawyer (~1%), total all-in cost",
      "MORTGAGE SCENARIO: if 70% LTV at 3.5% over 25yr — monthly payment, cash flow positive/negative",
      "FINANCIAL VERDICT: is this financially attractive? what yield threshold makes it a buy?"
    ]
  }},
  "agent_b": {{
    "score": <float 0-10>,
    "title": "Structural & Physical",
    "headline": "<key structural finding>",
    "analysis": [
      "BUILDING ERA: construction period implication for Porto building stock quality, common pathologies",
      "ENERGY CERT: efficiency class implications — typical utility costs, insulation, windows standard",
      "FLOOR & ORIENTATION: light exposure, noise risk, elevator access, flood/damp risk for ground floors",
      "AREA EFFICIENCY: is {area}m² realistic for {typ} in {freg}? layout efficiency estimate",
      "RENOVATION SCOPE: likely scope (cosmetic / light / medium / full gut) and cost estimate in €",
      "BUILDING HEALTH: common area maintenance expectation for this era/zone, condo fund adequacy",
      "AL SUITABILITY: physical suitability for AL (views, quiet, storage, kitchen quality expected)",
      "PRE-PURCHASE INSPECTION: 5 specific items to check before signing CPCV"
    ]
  }},
  "agent_c": {{
    "score": <float 0-10>,
    "title": "Legal & Regulatory",
    "headline": "<key legal finding>",
    "analysis": [
      "AL LICENSE: {freg} status — exact process, probability of obtaining license, timeline, risks",
      "PDM ZONING: expected zoning for {freg} (ARU? heritage? protected?), what is/isn't permitted",
      "HABITATION LICENSE: licença de utilização — what to verify, red flags if missing",
      "CADERNETA PREDIAL: key checks (typology, area match, Valor Patrimonial Tributário)",
      "REGISTO PREDIAL: charges, mortgages, easements, pre-emptive rights to verify",
      "CONDOMINIUM: typical bylaws risk for AL in {freg} buildings, how to check for existing AL prohibitions",
      "TAXES: IMT estimate for €{price:,} (rate bracket), annual IMI estimate, IRS on rental income",
      "LEGAL ROADMAP: step-by-step — lawyer engagement → due diligence → CPCV → escritura timeline"
    ]
  }},
  "agent_d": {{
    "score": <float 0-10>,
    "title": "Location & Market Dynamics",
    "headline": "<key location insight>",
    "analysis": [
      "NEIGHBORHOOD TRAJECTORY: gentrification stage for {freg} (early/mid/mature/peaked), 5-year outlook",
      "AL DEMAND: tourism flow for {freg}, seasonality pattern, occupancy expectations, competition density",
      "LTR DEMAND: tenant profile for {freg} (expats? students? professionals?), vacancy rate estimate",
      "TRANSPORT: nearest Metro stations, bus lines, walkability score, Porto Airport distance/access",
      "AMENITIES: supermarkets, restaurants, healthcare, schools/universities within walking distance",
      "COMPARABLE MARKET: similar properties in {freg} — price range, time on market, absorption rate",
      "GENTRIFICATION TRIGGERS: specific developments, infrastructure, or trends driving {freg} value",
      "PRICE OUTLOOK: 5-year appreciation — bull case / base case / bear case with reasoning"
    ]
  }},
  "agent_e": {{
    "score": <float 0-10>,
    "title": "Risk Matrix",
    "headline": "<highest-priority risk>",
    "analysis": [
      "REGULATORY RISK: AL law evolution risk (score 1-5), rent control expansion risk, specific {freg} risk",
      "MARKET RISK: Porto price correction probability — is market overheated? supply pipeline?",
      "STRUCTURAL RISK: hidden defect probability for this building era/type, cost range if issues found",
      "LIQUIDITY RISK: resale time estimate for {typ} at €{price:,} in {freg}, buyer pool depth",
      "CONCENTRATION RISK: single asset in single city — diversification considerations",
      "SPECIFIC RED FLAGS: any red flags from THIS property data (price anomaly, address issues, etc.)",
      "MACRO RISK: EUR interest rate outlook, Portugal economic trajectory, golden visa absence impact",
      "RISK MITIGATION: 3 concrete steps to reduce the top risks before and after purchase"
    ]
  }},
  "composite": <A*0.30 + B*0.15 + C*0.20 + D*0.20 + E*0.15>,
  "verdict": "<strong_buy|buy|hold|pass|strong_pass>",
  "investment_recommendation": "4-5 sentences: clear recommendation for this specific property. What is the investment thesis? What are the 2 most important conditions before proceeding? What would make this a strong buy vs. what would make you walk away?",
  "immediate_action_items": [
    "1. <most urgent step before making offer>",
    "2. <second step>",
    "3. <third step>",
    "4. <fourth step>",
    "5. <before signing CPCV>"
  ],
  "deal_breakers": ["<potential deal-breaker 1 if confirmed>", "<deal-breaker 2>"]
}}"""

    result = subprocess.run(
        ["claude", "-p", "--model", "claude-opus-4-7", prompt],
        capture_output=True, text=True, timeout=240,
        cwd=str(Path(__file__).parent.parent),
    )

    raw = result.stdout.strip()
    data = None
    for pat in [r"```json\s*([\s\S]+?)```", r"```\s*([\s\S]+?)```", r"(\{[\s\S]+\})"]:
        m = re.search(pat, raw)
        if m:
            try:
                data = json.loads(m.group(1))
                break
            except Exception:
                pass
    if not data:
        try:
            data = json.loads(raw)
        except Exception:
            data = {"error": raw[:2000], "composite": None, "verdict": "error"}

    metrics = {
        "price_m2": price_m2, "median_m2": median_m2, "vs_median_pct": vs_median_pct,
        "al_yield_pct": al_yield_pct, "ltr_yield_pct": ltr_yield_pct,
        "breakeven_occ_pct": breakeven_occ_pct, "al_status": al_status,
        "primary_url": primary_url, "al_rate": al_rate, "ltr_monthly": ltr_monthly,
    }
    html_report = _render_html(property_id, prop, listings, data, metrics)

    if send_email:
        _send_email_report(html_report, prop, data)

    return html_report


def _render_html(property_id, prop, listings, data, metrics):
    freg = prop.get("freguesia") or ""
    address = prop.get("address") or ""
    typ = prop.get("typology") or ""
    price = prop.get("price_eur") or 0
    area = prop.get("area_m2") or 0
    composite = data.get("composite")
    verdict = data.get("verdict", "")

    VERDICT_COLOR = {
        "strong_buy": "#22c55e", "buy": "#84cc16", "hold": "#eab308",
        "pass": "#f97316", "strong_pass": "#ef4444",
    }
    color = VERDICT_COLOR.get(verdict, "#888")

    agents = [
        ("agent_a", "A", "\U0001f4b0", "#3b82f6"),
        ("agent_b", "B", "\U0001f3d7️", "#8b5cf6"),
        ("agent_c", "C", "⚖️", "#ec4899"),
        ("agent_d", "D", "\U0001f4cd", "#14b8a6"),
        ("agent_e", "E", "⚠️", "#f97316"),
    ]

    agents_html = ""
    for key, letter, icon, clr in agents:
        ag = data.get(key, {})
        if not ag:
            continue
        sc = ag.get("score", 0)
        bar_w = int(sc * 10)
        items = ag.get("analysis", [])
        items_html = "".join(
            f'<li style="margin:8px 0;line-height:1.6">{i}</li>'
            for i in items
        )
        agents_html += f"""
<div style="background:#1a1f2e;border:1px solid #2a3045;border-radius:12px;padding:24px;margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
    <span style="font-size:24px">{icon}</span>
    <div style="flex:1">
      <div style="font-size:16px;font-weight:700;color:#e2e8f0">
        {letter} — {ag.get('title','')}
        <span style="float:right;font-size:22px;color:{clr};font-weight:800">{sc:.1f}</span>
      </div>
      <div style="font-size:13px;color:#94a3b8;margin-top:2px;font-style:italic">{ag.get('headline','')}</div>
    </div>
  </div>
  <div style="background:#111827;border-radius:6px;height:8px;margin-bottom:16px">
    <div style="width:{bar_w}%;height:8px;border-radius:6px;background:linear-gradient(90deg,{clr},{clr}88)"></div>
  </div>
  <ul style="color:#cbd5e1;font-size:14px;margin:0;padding-left:20px">{items_html}</ul>
</div>"""

    action_items = data.get("immediate_action_items", [])
    actions_html = "".join(
        f'<li style="margin:8px 0;color:#94a3b8;font-size:14px">{a}</li>'
        for a in action_items
    )

    deal_breakers = data.get("deal_breakers", [])
    db_html = "".join(
        f'<li style="margin:6px 0;color:#fca5a5;font-size:14px">\U0001f6ab {d}</li>'
        for d in deal_breakers
    )

    sources_html = " ".join(
        f'<a href="{l["url"]}" target="_blank" style="color:#60a5fa;font-size:12px;'
        f'text-decoration:none;background:#1e293b;padding:3px 8px;border-radius:4px">'
        f'{l["source"]}</a>'
        for l in listings if l.get("url")
    )

    comp_display = f"{composite:.1f}" if composite is not None else "N/A"
    error_section = ""
    if "error" in data:
        error_section = f'<pre style="color:#fca5a5;font-size:11px;background:#1a0a0a;padding:12px;border-radius:8px;overflow:auto">{data["error"]}</pre>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>PESSOA Investigation #{property_id}</title>
<style>
  body{{background:#0d1117;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;margin:0;padding:24px}}
  @media(max-width:600px){{body{{padding:12px}}}}
</style>
</head>
<body>
<div style="max-width:860px;margin:0 auto">

  <div style="text-align:center;margin-bottom:32px">
    <div style="font-size:11px;color:#64748b;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px">PESSOA FULL INVESTIGATION</div>
    <div style="font-size:22px;font-weight:700;color:#e2e8f0">{address[:80]}</div>
    <div style="font-size:14px;color:#64748b;margin-top:4px">{typ} · {area}m² · €{price:,} · {freg}</div>
    <div style="margin-top:8px">{sources_html}</div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:28px">
    <div style="background:#1a1f2e;border-radius:10px;padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:800;color:{color}">{comp_display}</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px;text-transform:uppercase">{verdict.replace('_',' ')}</div>
    </div>
    <div style="background:#1a1f2e;border-radius:10px;padding:16px;text-align:center">
      <div style="font-size:22px;font-weight:700;color:#60a5fa">{metrics['al_yield_pct']}%</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">AL Net Yield (est.)</div>
    </div>
    <div style="background:#1a1f2e;border-radius:10px;padding:16px;text-align:center">
      <div style="font-size:22px;font-weight:700;color:#34d399">{metrics['ltr_yield_pct']}%</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">LTR Net Yield (est.)</div>
    </div>
  </div>

  <div style="background:#1a1f2e;border:1px solid #2a3045;border-radius:12px;padding:20px;margin-bottom:20px">
    <div style="font-size:13px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">\U0001f4cb Property Summary</div>
    <p style="color:#cbd5e1;font-size:15px;line-height:1.7;margin:0">{data.get('property_summary','')}</p>
  </div>

  {error_section}
  {agents_html}

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
    <div style="background:#1a1f2e;border:1px solid #2a3045;border-radius:12px;padding:20px">
      <div style="font-size:13px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">⚡ Immediate Action Items</div>
      <ol style="margin:0;padding-left:18px">{actions_html}</ol>
    </div>
    <div style="background:#1a1f2e;border:1px solid #3a1c1c;border-radius:12px;padding:20px">
      <div style="font-size:13px;font-weight:600;color:#f87171;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">\U0001f6ab Potential Deal Breakers</div>
      <ul style="margin:0;padding-left:18px">{db_html if db_html else '<li style="color:#64748b;font-size:14px">None identified</li>'}</ul>
    </div>
  </div>

  <div style="background:linear-gradient(135deg,#1a2040,#1e1a2e);border:1px solid #3a3060;border-radius:12px;padding:24px;margin-bottom:20px">
    <div style="font-size:13px;font-weight:600;color:#a78bfa;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">\U0001f3af Investment Recommendation</div>
    <p style="color:#e2e8f0;font-size:15px;line-height:1.8;margin:0">{data.get('investment_recommendation','')}</p>
  </div>

  <div style="text-align:center;font-size:11px;color:#374151;padding:16px">
    Generated by PESSOA · claude-opus-4-7 · {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </div>
</div>
</body>
</html>"""


def _send_email_report(html_report: str, prop: dict, data: dict):
    env_path = Path(__file__).parent.parent / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()

    url = env.get("GMAIL_API_URL")
    token = env.get("GMAIL_API_TOKEN")
    if not url or not token:
        return

    address = prop.get("address") or f"Property #{prop.get('id')}"
    verdict = data.get("verdict", "")
    composite = data.get("composite")
    subject = f"PESSOA Investigation: {address[:60]} | {composite:.1f} {verdict}" if composite else f"PESSOA Investigation: {address[:60]}"

    try:
        requests.post(
            url,
            json={
                "token": token,
                "to": "vetrinarbatyam@gmail.com,vet_batyam@yahoo.com",
                "subject": subject,
                "html": html_report,
            },
            timeout=30,
        )
    except Exception as e:
        print(f"[email] failed: {e}")
