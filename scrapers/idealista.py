"""FAROL scraper — Idealista.pt (Porto centro)."""
from .base import SourceScraper, RawListing, browser, polite_delay, parse_price, parse_area, parse_typology, infer_freguesia


class IdealistaScraper(SourceScraper):
    source = "idealista"
    # Porto centro pre-filtered by freguesia-level geo. Idealista URL shape:
    base_url = (
        "https://www.idealista.pt/comprar-casas/porto/"
        "com-preco-max_{budget_max},preco-min_{budget_min},tamanho-maximo_999,publicado_ultimo-mes/"
    )

    def scrape(self, budget_min=150_000, budget_max=650_000):
        url = self.base_url.format(budget_min=budget_min, budget_max=budget_max)
        self.log(f"opening {url}")
        with browser() as ctx:
            page = ctx.new_page()
            for pagenum in range(1, self.max_pages + 1):
                purl = url if pagenum == 1 else f"{url}pagina-{pagenum}.htm"
                try:
                    page.goto(purl, timeout=30_000)
                except Exception as e:
                    self.log(f"goto fail p{pagenum}: {e}")
                    break
                # Idealista often shows DataDome captcha
                if "datadome" in page.content().lower() or page.query_selector("[class*='captcha']"):
                    self.log("DataDome/captcha — abort. Run manually with headful browser or proxy.")
                    break
                cards = page.query_selector_all("article.item, .item-info-container")
                if not cards:
                    self.log(f"no cards p{pagenum} — stop")
                    break
                for card in cards:
                    try:
                        a = card.query_selector("a.item-link")
                        if not a:
                            continue
                        href = a.get_attribute("href") or ""
                        link = "https://www.idealista.pt" + href if href.startswith("/") else href
                        if link in self.seen:
                            continue
                        self.seen.add(link)
                        title = (a.inner_text() or "").strip()
                        price_txt = card.inner_text() if card else ""
                        price = parse_price((card.query_selector(".item-price") or card).inner_text())
                        typ = parse_typology(title)
                        area = parse_area(card.inner_text())
                        addr = title
                        freg = infer_freguesia(title + " " + addr, link)
                        ext_id = href.strip("/").split("/")[-1] or href
                        yield RawListing(
                            source=self.source, external_id=ext_id, url=link,
                            title=title, address=addr, freguesia=freg,
                            typology=typ, area_m2=area, price_eur=price,
                            raw={"html_snippet": card.inner_text()[:400]},
                        )
                    except Exception as e:
                        self.log(f"card parse fail: {e}")
                polite_delay()
