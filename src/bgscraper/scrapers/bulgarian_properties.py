"""bulgarianproperties.com scraper — English-language Bulgarian agency."""
from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ..constants import PropertyType
from ..logging_setup import get_logger
from .base import BaseScraper, RawListing, SearchConfig
from .registry import register

log = get_logger(__name__)

_BASE = "https://www.bulgarianproperties.com"

_TYPE_SLUGS: dict[PropertyType, str] = {
    PropertyType.APARTMENT_3ROOM: "3-bedroom_apartments",
    PropertyType.HOUSE: "Houses",
}

# Sofia-area location suffixes in detail URLs (e.g. "_in_Sofia", "_in_Pancharevo").
_SOFIA_LOCATIONS = (
    "_in_Sofia", "_in_Pancharevo", "_in_Dragalevtsi", "_in_Boyana",
    "_in_Simeonovo", "_in_Bistritsa", "_in_Zheleznitsa", "_in_German",
)

# Listing URL: /AD{code}BG_...
_ID_RE = re.compile(r"/AD(\d+)BG")
_AREA_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:sq\.?\s*m|кв\.?\s*м|m2|m²)", re.I)
_PRICE_RE = re.compile(r"([\d\s.,]+)\s*(EUR|€|BGN|лв)", re.I)


def _abs(url: str) -> str:
    if url.startswith("/"):
        return _BASE + url
    return url


@register
class BulgarianPropertiesScraper(BaseScraper):
    source = "bulgarianproperties.com"

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
        for page in range(1, self.settings.max_list_pages + 1):
            if page == 1:
                yield f"{_BASE}/{slug}_in_Bulgaria/index.html"
            else:
                yield f"{_BASE}/{slug}_in_Bulgaria/index{page - 1}.html"

    def parse_list_page(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = _ID_RE.search(href)
            if not m:
                continue
            full = _abs(href)
            # Results are country-wide; keep only Sofia-area listings.
            if not any(loc in full for loc in _SOFIA_LOCATIONS):
                continue
            if full not in seen:
                seen.add(full)
                urls.append(full)
        log.debug("bulgarianproperties.list_parsed", url=base_url, count=len(urls))
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
        h = soup.find("h1") or soup.find("h2")
        if h:
            title = h.get_text(strip=True)

        price_raw, currency_raw = None, None
        for pm in _PRICE_RE.finditer(text):
            amt, cur = pm.group(1).strip(), pm.group(2).strip().upper()
            if cur in ("EUR", "€"):
                price_raw, currency_raw = amt, "EUR"
                break
            if cur in ("BGN", "ЛВ"):
                price_raw, currency_raw = amt, "BGN"

        # This site uses English — "Sofia, Lozenets quarter"
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
        if "furnished" in low:
            if "unfurnished" in low:
                furnishing_raw = "unfurnished"
            elif "partially furnished" in low:
                furnishing_raw = "partially furnished"
            else:
                furnishing_raw = "furnished"

        description = None
        for sel in ("div.description", "div.property-description", "div#description"):
            el = soup.select_one(sel)
            if el:
                description = el.get_text(" ", strip=True)[:2000]
                break

        images: list[str] = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if "bulgarianproperties" in src and ("/photos/" in src or "/images/" in src):
                full_src = src if src.startswith("http") else _BASE + src
                if full_src not in images:
                    images.append(full_src)

        agency = "Bulgarian Properties"

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

    @staticmethod
    def _extract_neighborhood(text: str) -> str | None:
        # English patterns: "Sofia, Lozenets" or "Sofia - Boyana quarter"
        loc_re = re.compile(
            r"Sofia\s*[,\-–]\s*([A-Za-zА-Яа-яёЁ\s\-\.]+?)(?:\s*(?:quarter|район|\d|[,|]|\n)|\s*$)",
            re.I,
        )
        m = loc_re.search(text)
        if m:
            return m.group(1).strip().rstrip(".,;- ")
        # Bulgarian fallback.
        loc_re_bg = re.compile(
            r"Софи[яй]\s*[,\-–]\s*([A-Za-zА-Яа-яёЁ\s\-\.]+?)(?:\s*(?:\d|[,|]|\n)|\s*$)",
            re.I,
        )
        m2 = loc_re_bg.search(text)
        if m2:
            return m2.group(1).strip().rstrip(".,;- ")
        return None
