"""olx.bg scraper — real estate classifieds section."""
from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ..constants import PropertyType
from ..logging_setup import get_logger
from .base import BaseScraper, RawListing, SearchConfig
from .registry import register

log = get_logger(__name__)

_BASE = "https://www.olx.bg"

# OLX category slugs for property types.
_TYPE_SLUGS: dict[PropertyType, str] = {
    PropertyType.APARTMENT_3ROOM: "apartamenti",
    PropertyType.HOUSE: "kaschi-vili",
}

# OLX listing ID pattern: -ID{alphanum}.html
_ID_RE = re.compile(r"-ID([a-zA-Z0-9]+)\.html")
_AREA_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:кв\.?\s*м|m2|m²)", re.I)
_PRICE_RE = re.compile(r"([\d\s.,]+)\s*(лв\.?|BGN|€|EUR)", re.I)


def _abs(url: str) -> str:
    if url.startswith("/"):
        return _BASE + url
    return url


@register
class OlxBgScraper(BaseScraper):
    source = "olx.bg"

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
        slug = cfg.extra["slug"]
        base = f"{_BASE}/nedvizhimi-imoti/prodazhbi/{slug}/sofiya/"
        for page in range(1, self.settings.max_list_pages + 1):
            if page == 1:
                yield base
            else:
                yield f"{base}?page={page}"

    def parse_list_page(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/d/ad/" not in href:
                continue
            full = _abs(href)
            # Strip query params for dedup.
            clean = full.split("?")[0]
            if clean not in seen:
                seen.add(clean)
                urls.append(clean)
        log.debug("olx_bg.list_parsed", url=base_url, count=len(urls))
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
        h = soup.find("h1") or soup.find("h4")
        if h:
            title = h.get_text(strip=True)

        price_raw, currency_raw = None, None
        # OLX shows "332491.10 лв. / 170000 €" — prefer EUR.
        eur_m = re.search(r"([\d\s.,]+)\s*€", text)
        if eur_m:
            price_raw, currency_raw = eur_m.group(1).strip(), "EUR"
        else:
            for pm in _PRICE_RE.finditer(text):
                amt, cur = pm.group(1).strip(), pm.group(2).strip().lower()
                if cur in ("лв", "лв.", "bgn"):
                    price_raw, currency_raw = amt, "BGN"
                    break

        neighborhood_raw = self._extract_neighborhood(text)

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
        for sel in ("div.css-1t507yq", "div[data-cy='ad_description']", "div.description"):
            el = soup.select_one(sel)
            if el:
                description = el.get_text(" ", strip=True)[:2000]
                break

        images: list[str] = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if ("olxcdn" in src or "olx.bg" in src) and "/photos/" in src:
                if src not in images:
                    images.append(src)

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
        )

    @staticmethod
    def _extract_neighborhood(text: str) -> str | None:
        # OLX shows "гр. София, Лозенец" or "Sofia, Lozenets"
        loc_re = re.compile(
            r"(?:гр\.?\s*)?Софи[яй]\s*[,\-–]\s*"
            r"([A-Za-zА-Яа-яёЁ\s\-\.]+?)"
            r"(?:\s*[-–·•|,\d\n]|\s*$)",
            re.I,
        )
        m = loc_re.search(text)
        if m:
            return m.group(1).strip().rstrip(".,;- ")
        return None
