"""PESSOA Suite — Central configuration."""
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "listings.db"
DASH_OUT = ROOT / "dashboard" / "out"
LOGS = ROOT / "logs"

# --- Geofilter: Porto expanded scope (UNESCO core + commercial + bohemian + peripheral-relevant) ---
FREGUESIAS = {
    # Gerlic heritage core (UNESCO)
    "Ribeira":         ["ribeira"],
    "Sé":              ["se-porto", "-se-", "sé", "catedral"],
    "Miragaia":        ["miragaia"],
    # Commercial centre
    "Baixa":           ["baixa", "aliados", "sao-bento", "são-bento", "s-bento", "s.bento"],
    "Santo Ildefonso": ["santo-ildefonso", "santo_ildefonso", "ildefonso", "bolhão", "bolhao", "santa-catarina", "santa_catarina"],
    "Vitória":         ["vitória", "vitoria"],
    "São Nicolau":     ["são-nicolau", "sao-nicolau", "nicolau"],
    # Bohemian / culture
    "Cedofeita":       ["cedofeita"],
    "Bonfim":          ["bonfim", "heroísmo", "heroismo", "campo-24", "campo_24"],
    # Peripheral — relevant by user's mandate
    "Massarelos":      ["massarelos", "palacio-de-cristal", "palácio-de-cristal", "jardins-do-palacio"],
    "Boavista":        ["boavista", "casa-da-musica", "casa-da-música"],
    "Campanhã":        ["campanha", "campanhã", "freixo"],
}

FREGUESIA_MEDIANS_EUR_PER_M2 = {
    # Core — highest prices
    "Ribeira": 5500, "Sé": 5200, "Miragaia": 4900,
    # Commercial
    "Baixa": 5100, "Santo Ildefonso": 4700, "Vitória": 4700, "São Nicolau": 5000,
    # Bohemian
    "Cedofeita": 4600, "Bonfim": 4100,
    # Peripheral
    "Massarelos": 4300, "Boavista": 4600, "Campanhã": 3800,
}

# Character notes — used in PESSOA prompts for neighborhood-aware analysis
FREGUESIA_PROFILE = {
    "Ribeira": "UNESCO core · riverfront medieval · maximum tourist draw · AL premium ADR",
    "Sé": "cathedral quarter above Ribeira · narrow streets · heritage-restricted · AL premium",
    "Miragaia": "quiet western waterfront · old port · less tourist-saturated",
    "Baixa": "modern commercial hub · Liberdade · metro/rail interchange",
    "Santo Ildefonso": "Santa Catarina shopping · Bolhão market · central residential",
    "Vitória": "historic residential · Clérigos nearby",
    "São Nicolau": "port-wine heritage · riverside",
    "Cedofeita": "bohemian · galleries · student/digital-nomad · 'Porto's Florentin'",
    "Bonfim": "trendy · azulejo · independent cafés · AL-released 2024",
    "Massarelos": "riverside parks · Cristal Palace · tram museum · quieter family-oriented",
    "Boavista": "modern west · Casa da Música · business district · corporate tenants",
    "Campanhã": "east · main train station (Souto de Moura redevelopment) · emerging gentrification",
}

# --- Filters ---
TYPOLOGY_ALLOWED = {"T0", "T1", "T2", "T3"}
BUDGET_MIN = 150_000
BUDGET_MAX = 650_000
THESIS = "hybrid"  # LTR + AL

# --- Scan behaviour ---
SCAN_DAYS_INITIAL = 30
SCAN_DAYS_WEEKLY = 7
PESSOA_TOP_N_INITIAL = 50
PESSOA_TOP_N_WEEKLY = 20
CRIVO_PRICE_M2_TOLERANCE = 0.40  # ±40% vs freguesia median

# --- Dedup ---
DEDUP_PRICE_TOL = 0.05     # ±5%
DEDUP_AREA_TOL_M2 = 2
DEDUP_ADDRESS_FUZZ = 88    # rapidfuzz threshold 0-100

# --- Scraper politeness ---
REQUEST_DELAY_S = (2.0, 5.0)   # random between
PAGES_PER_SOURCE = 20
HEADLESS = True
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# --- Sources (4 boards + Custojusto = 5 total) ---
SOURCES = ["idealista", "imovirtual", "casa_sapo", "supercasa", "custojusto"]

# Base search URLs for Porto centro (these are templates; each scraper appends pagination/filters)
SOURCE_URLS = {
    "idealista":  "https://www.idealista.pt/comprar-casas/porto/com-preco-max_{max}/",
    "imovirtual": "https://www.imovirtual.com/pt/resultados/comprar/apartamento/porto/porto?limit=36&priceMax={max}",
    "casa_sapo":  "https://casa.sapo.pt/comprar-apartamentos/porto/?gp={max}",
    "supercasa":  "https://www.supercasa.pt/comprar/apartamentos/porto-porto?pmax={max}",
    "custojusto": "https://www.custojusto.pt/imobiliario/comprar/apartamento-moradia?o=1&lrp={max}",
}

# --- Notifications ---
NOTIFY_WHATSAPP_NUMBER = "972543123419"  # Gil
NOTIFY_GMAIL_ADDRS = ["vetrinarbatyam@gmail.com", "vet_batyam@yahoo.com"]
NOTIFY_THRESHOLD_COMPOSITE = 7.5
