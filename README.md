# PESSOA Suite · Porto Centro Property Intelligence

Two-stage Portuguese property scanner + deep analyser, focused on the historic centre of Porto.

- **FAROL** — scans 5 property boards (Idealista, Imovirtual, Casa Sapo, Supercasa, Custojusto)
  with a 6-sub-agent pipeline (5 scrapers + Fusão dedup + Crivo triage).
- **PESSOA Deep** — 5-sub-agent deep due-diligence on the top candidates
  (Financial, Structural, Legal, Location, Risk).
- **Dashboard** — bilingual Hebrew/Portuguese web view, Top 20 by composite + tabs per sub-agent.

## Setup

```bash
# already done during install, but for reference:
python -m venv .venv
.venv/Scripts/python.exe -m pip install playwright requests rapidfuzz jinja2 python-dotenv
.venv/Scripts/python.exe -m playwright install chromium --with-deps
```

## First Run (30-day backfill)

```bash
bash cron/initial.sh
```

This runs: FAROL scan → Fusão dedup → Crivo triage → PESSOA top 50 → dashboard.

Logs: `logs/initial-YYYYMMDD-HHMM.log`.

## Weekly Run

```bash
bash cron/weekly.sh
```

Or install as a Windows Scheduled Task (Monday 06:00):

```powershell
powershell -ExecutionPolicy Bypass -File cron/install_task_scheduler.ps1
```

## Structure

```
porto-pessoa/
├── config.py                 # freguesias, budget, thresholds
├── db/
│   ├── schema.sql
│   └── listings.db
├── scrapers/                 # FAROL sub-agents 1-4 (5 sites)
│   ├── base.py               # shared Playwright helpers
│   ├── idealista.py
│   ├── imovirtual.py
│   ├── casa_sapo.py
│   ├── supercasa.py
│   └── custojusto.py
├── pipeline/
│   ├── fusao.py              # sub-agent 5: dedup
│   ├── crivo.py              # sub-agent 6: triage
│   ├── run_scan.py           # FAROL entry point
│   ├── pessoa_orchestrator.py # PESSOA deep via Claude CLI
│   └── seed_demo.py          # demo data seeder
├── dashboard/
│   ├── generate.py           # list view + drill-down HTML
│   └── out/                  # rendered output
├── notify/
│   ├── summary.py            # build WA + Gmail payloads
│   └── send.py               # dispatch via claude CLI
├── cron/
│   ├── initial.sh
│   ├── weekly.sh
│   └── install_task_scheduler.ps1
└── logs/
```

## Configuration (`config.py`)

| Key | Value |
|---|---|
| Freguesias | Sé · São Nicolau · Vitória · Miragaia · Cedofeita · Santo Ildefonso · Bonfim-West |
| Typology | T0 · T1 · T2 · T3 |
| Budget | €150k – €650k |
| Thesis | hybrid (LTR + AL) |
| PESSOA top N (initial) | 50 |
| PESSOA top N (weekly) | 20 |
| Notify threshold | composite ≥ 7.5 |
| WhatsApp | 0543123419 (Gil) |
| Gmail | vetrinarbatyam@gmail.com, vet_batyam@yahoo.com |

## Known Limitations (first 2 weeks)

1. **Anti-bot defences** — Idealista uses DataDome, will likely block headless Chromium
   from a residential IP within ~50 requests. Run initial in chunks, or reduce `PAGES_PER_SOURCE`.
2. **Selector drift** — scraper CSS selectors may need tuning after first run; each
   scraper logs "no cards p{N} — stop" if the DOM changed.
3. **PESSOA cost** — 50 properties × 5 sub-agents = 250 Claude calls per initial run.
   Budget accordingly.

## Dashboard

After any run:

```
file:///C:/Users/user/porto-pessoa/dashboard/out/index.html
```

Six tabs: ציון מצרפי (composite), and five per-sub-agent views. Click any row
to see the full deep-dive for that property, with links to every board it appeared on.
