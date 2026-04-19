"""FAROL — shared Playwright scraper base."""
import hashlib
import random
import re
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import HEADLESS, USER_AGENT, REQUEST_DELAY_S, FREGUESIAS, TYPOLOGY_ALLOWED, BUDGET_MIN, BUDGET_MAX


@dataclass
class RawListing:
    """One raw listing from one source before dedup."""
    source: str
    external_id: str
    url: str
    title: str = ""
    address: str = ""
    freguesia: str = ""
    typology: str = ""           # T0/T1/T2/T3
    area_m2: int = 0
    price_eur: int = 0
    built_year: Optional[int] = None
    energy_cert: str = ""
    floor: str = ""
    condominio_eur: Optional[int] = None
    description: str = ""
    photo_url: str = ""
    raw: dict = field(default_factory=dict)

    def canonical_hash(self) -> str:
        """Stable hash for dedup. Not perfect — Fusão does the fuzzy match."""
        norm_addr = re.sub(r'\W+', '', self.address.lower())[:40]
        price_bucket = (self.price_eur // 5000) * 5000 if self.price_eur else 0
        key = f"{norm_addr}|{self.typology}|{self.area_m2}|{price_bucket}"
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    def price_per_m2(self) -> float:
        return round(self.price_eur / self.area_m2, 1) if self.area_m2 else 0.0

    def in_scope(self) -> bool:
        """Quick whitelist check before saving."""
        if self.typology and self.typology not in TYPOLOGY_ALLOWED:
            return False
        if self.price_eur and not (BUDGET_MIN <= self.price_eur <= BUDGET_MAX):
            return False
        if self.freguesia and self.freguesia not in FREGUESIAS:
            return False
        return True


def infer_freguesia(text: str, url: str = "") -> str:
    """Match any freguesia alias in text or URL slug. URL is more reliable."""
    # Prefer URL slug (Casa Sapo / Imovirtual encode real freguesia in path)
    sources = [url.lower(), text.lower()]
    for src in sources:
        if not src:
            continue
        for name, aliases in FREGUESIAS.items():
            for a in aliases:
                if a in src:
                    return name
    return ""


def parse_typology(text: str) -> str:
    """Extract Tn classification."""
    m = re.search(r'\bT([0-6])\b', text.upper())
    return f"T{m.group(1)}" if m else ""


def parse_area(text: str) -> int:
    """Extract area in m² (tolerates m2, m², m<sup>2</sup>)."""
    m = re.search(r'(\d{2,4})\s*m\s*[²2]', text, re.I)
    return int(m.group(1)) if m else 0


def parse_price(text: str) -> int:
    """Extract EUR price. Handles PT formats: '450.000 €', '€ 450 000', '450000€'."""
    candidates = re.findall(
        r'(?<![\w.,])(\d{1,3}(?:[.\s,]\d{3})+|\d{4,7})(?!\w)', text
    )
    for raw in candidates:
        n = int(re.sub(r'\D', '', raw))
        if 50_000 <= n <= 2_000_000:
            return n
    return 0


def polite_delay():
    time.sleep(random.uniform(*REQUEST_DELAY_S))


@contextmanager
def browser():
    """Context-managed Playwright browser with stealth defaults."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = br.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        try:
            yield ctx
        finally:
            br.close()


class SourceScraper:
    """Subclass per source; override `scrape()`."""
    source: str = ""
    base_url: str = ""

    def __init__(self, max_pages: int = 20):
        self.max_pages = max_pages
        self.seen: set[str] = set()

    def scrape(self) -> Iterator[RawListing]:
        raise NotImplementedError

    def log(self, msg: str):
        print(f"[{self.source}] {msg}", flush=True)
