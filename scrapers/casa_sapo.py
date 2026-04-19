"""FAROL scraper — Casa Sapo."""
from .base import SourceScraper, RawListing, browser, polite_delay, parse_price, parse_area, parse_typology, infer_freguesia


class CasaSapoScraper(SourceScraper):
    source = "casa_sapo"
    base_url = (
        "https://casa.sapo.pt/comprar-apartamentos/porto/"
        "?gp={budget_max}&gps={budget_min}"
    )

    def scrape(self, budget_min=150_000, budget_max=650_000):
        url = self.base_url.format(budget_min=budget_min, budget_max=budget_max)
        self.log(f"opening {url}")
        with browser() as ctx:
            page = ctx.new_page()
            for pagenum in range(1, self.max_pages + 1):
                purl = url + f"&p={pagenum}" if pagenum > 1 else url
                try:
                    page.goto(purl, timeout=30_000)
                    page.wait_for_timeout(1500)
                except Exception as e:
                    self.log(f"goto fail p{pagenum}: {e}")
                    break
                cards = page.query_selector_all(".searchPropertyListItem, .property")
                if not cards:
                    cards = page.query_selector_all("article, [class*='property']")
                if not cards:
                    self.log(f"no cards p{pagenum} — stop")
                    break
                for card in cards:
                    try:
                        a = card.query_selector("a[href*='/detalhes/'], a[href*='/imovel/'], a")
                        if not a:
                            continue
                        href = a.get_attribute("href") or ""
                        link = href if href.startswith("http") else "https://casa.sapo.pt" + href
                        if link in self.seen:
                            continue
                        self.seen.add(link)
                        text = card.inner_text() or ""
                        title = text.splitlines()[0][:160] if text else ""
                        price = parse_price(text)
                        typ = parse_typology(text)
                        area = parse_area(text)
                        freg = infer_freguesia(text, link)
                        ext_id = link.split("/")[-1][:30]
                        yield RawListing(
                            source=self.source, external_id=ext_id, url=link,
                            title=title, address=title, freguesia=freg,
                            typology=typ, area_m2=area, price_eur=price,
                            raw={"html_snippet": text[:400]},
                        )
                    except Exception as e:
                        self.log(f"card parse fail: {e}")
                polite_delay()
