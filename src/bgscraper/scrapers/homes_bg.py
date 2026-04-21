"""homes.bg scraper."""
from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ..constants import PropertyType
from ..logging_setup import get_logger
from .base import BaseScraper, RawListing, SearchConfig
from .registry import register

log = get_logger(__name__)

_BASE = "https://www.homes.bg"

_TYPE_SLUGS: dict[PropertyType, str] = {
    PropertyType.APARTMENT_3ROOM: "tristaen",
    PropertyType.HOUSE: "kashta",
}

# homes.bg listing URL: /offer/apartament-za-prodazhba/.../as{id}
_ID_RE = re.compile(r"/as(\d+)$")
_AREA_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:кв\.?\s*м|m2|m²)", re.I)
_PRICE_RE = re.compile(r"([\d\s.,]+)\s*(EUR|лв|BGN|€)", re.I)


def _abs(url: str) -> str:
    if url.startswith("/"):
        return _BASE + url
    return url


@register
class HomesBgScraper(BaseScraper):
    source = "homes.bg"

    def _build_search_configs(self) -> list[SearchConfig]:
        configs: list[SearchConfig] = []
        for ptype, slug in _TYPE_SLUGS.items():
            cap = (
                self.settings.price_cap_apartment_eur
                if ptype == PropertyType.APARTMENT_3ROOM
                else self.settings.price_cap_house_eur
            )
            configs.append(SearchConfig(
                property_type=ptype,
                price_cap_eur=cap,
                extra={"slug": slug},
            ))
        return configs

    def iter_list_pages(self, cfg: SearchConfig) -> Iterator[str]:
        # homes.bg search uses query params on the homepage
        slug = cfg.extra["slug"]
        for page in range(1, self.settings.max_list_pages + 1):
            yield f"{_BASE}/?search=&filter_type={slug}&filter_city=sofiya&page={page}"

    def parse_list_page(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/offer/" not in href:
                continue
            full = _abs(href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        log.debug("homes_bg.list_parsed", url=base_url, count=len(urls))
        return urls

    def parse_detail(self, html: str, url: str, cfg: SearchConfig) -> RawListing:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        source_id = ""
        m = _ID_RE.search(url)
        if m:
            source_id = m.group(1)
        else:
            source_id = url.rstrip("/").rsplit("/", 1)[-1]

        title = None
        h = soup.find("h2") or soup.find("h1")
        if h:
            title = h.get_text(strip=True)

        price_raw, currency_raw = None, None
        for pm in _PRICE_RE.finditer(text):
            amt, cur = pm.group(1).strip(), pm.group(2).strip().upper()
            if cur in ("EUR", "€"):
                price_raw, currency_raw = amt, "EUR"
                break
            if cur in ("ЛВ", "BGN"):
                price_raw, currency_raw = amt, "BGN"

        neighborhood_raw = None
        if title and "," in title:
            neighborhood_raw = title.split(",")[0].strip()

        area_sqm = None
        am = _AREA_RE.search(text)
        if am:
            try:
                area_sqm = float(am.group(1).replace(" ", "").replace(",", "."))
            except ValueError:
                pass

        furnishing_raw = None
        low = text.lower()
        if "обзаведен" in low:
            furnishing_raw = "необзаведен" if "необзаведен" in low else "обзаведен"

        description = None
        for sel in ("div.description", "div.offer-description"):
            el = soup.select_one(sel)
            if el:
                description = el.get_text(" ", strip=True)[:2000]
                break
        if not description:
            ps = soup.find_all("p")
            if ps:
                longest = max(ps, key=lambda p: len(p.get_text(strip=True)))
                t = longest.get_text(" ", strip=True)
                if len(t) > 50:
                    description = t[:2000]

        images: list[str] = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if "homes.bg" in src and src not in images:
                images.append(src if src.startswith("http") else "https:" + src)

        agency = None
        for a_tag in soup.find_all("a", href=True):
            if "/companies/" in a_tag.get("href", ""):
                agency = a_tag.get_text(strip=True)
                break

        return RawListing(
            source=self.source,
            source_id=source_id,
            url=url,
            title=title,
            price_raw=price_raw,
            currency_raw=currency_raw,
            property_type_raw=cfg.extra["slug"],
            property_type=cfg.property_type,
            neighborhood_raw=neighborhood_raw,
            area_sqm=area_sqm,
            furnishing_raw=furnishing_raw,
            description=description,
            images=images,
            agency=agency,
        )
