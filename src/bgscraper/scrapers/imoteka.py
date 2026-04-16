"""imoteka.bg scraper."""
from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from ..constants import PropertyType
from ..logging_setup import get_logger
from .base import BaseScraper, RawListing, SearchConfig
from .registry import register

log = get_logger(__name__)

_BASE = "https://www.imoteka.bg"

# imoteka.bg uses location+type IDs: l4451=Sofia, t3=tristaen, t15=house/villa.
_TYPE_PARAMS: dict[PropertyType, dict[str, str]] = {
    PropertyType.APARTMENT_3ROOM: {
        "path": "sofiya-tristaen-apartament",
        "code": "l4451t3",
        "label": "tristaen",
    },
    PropertyType.HOUSE: {
        "path": "sofiya-kashta-vila",
        "code": "l4451t15",
        "label": "kashta",
    },
}

# Listing URL: /sofiya-{hood}-{type}-offer{id}
_ID_RE = re.compile(r"offer(\d+)")
_AREA_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:кв\.?\s*м|m2|m²)", re.I)
_PRICE_RE = re.compile(r"([\d\s.,]+)\s*(EUR|евро|€|лв\.?|BGN)", re.I)


def _abs(url: str) -> str:
    if url.startswith("/"):
        return _BASE + url
    return url


@register
class ImotekaScraper(BaseScraper):
    source = "imoteka.bg"

    def _build_search_configs(self) -> list[SearchConfig]:
        configs: list[SearchConfig] = []
        for ptype, params in _TYPE_PARAMS.items():
            cap = (
                self.settings.price_cap_apartment_eur
                if ptype == PropertyType.APARTMENT_3ROOM
                else self.settings.price_cap_house_eur
            )
            configs.append(SearchConfig(
                property_type=ptype,
                price_cap_eur=cap,
                extra=params,
            ))
        return configs

    def iter_list_pages(self, cfg: SearchConfig) -> Iterator[str]:
        path = cfg.extra["path"]
        code = cfg.extra["code"]
        for page in range(1, self.settings.max_list_pages + 1):
            if page == 1:
                yield f"{_BASE}/sale/{path}/{code}"
            else:
                yield f"{_BASE}/sale/{path}/{code}?page={page}"

    def parse_list_page(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "offer" not in href:
                continue
            m = _ID_RE.search(href)
            if not m:
                continue
            full = _abs(href)
            if full not in seen:
                seen.add(full)
                urls.append(full)
        log.debug("imoteka.list_parsed", url=base_url, count=len(urls))
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
            amt, cur = pm.group(1).strip(), pm.group(2).strip().lower()
            if cur in ("eur", "евро", "€"):
                price_raw, currency_raw = amt, "EUR"
                break
            if cur in ("лв", "лв.", "bgn"):
                price_raw, currency_raw = amt, "BGN"

        neighborhood_raw = self._extract_neighborhood(text, url)

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
        for sel in ("div.description", "div.offer-description", "div.text"):
            el = soup.select_one(sel)
            if el:
                description = el.get_text(" ", strip=True)[:2000]
                break

        images: list[str] = []
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if "imoteka" in src and ("/photos/" in src or "/offer/" in src):
                full_src = src if src.startswith("http") else "https:" + src
                if full_src not in images:
                    images.append(full_src)

        agency = "Имотека"

        return RawListing(
            source=self.source,
            source_id=source_id,
            url=url,
            title=title,
            price_raw=price_raw,
            currency_raw=currency_raw,
            property_type_raw=cfg.extra["label"],
            property_type=cfg.property_type,
            neighborhood_raw=neighborhood_raw,
            area_sqm=area_sqm,
            furnishing_raw=furnishing_raw,
            description=description,
            images=images,
            agency=agency,
        )

    @staticmethod
    def _extract_neighborhood(text: str, url: str) -> str | None:
        loc_re = re.compile(
            r"Софи[яй]\s*[,\-–]\s*([A-Za-zА-Яа-яёЁ\s\-\.]+?)(?:\s*(?:\d|[,|]|\n)|\s*$)",
            re.I,
        )
        m = loc_re.search(text)
        if m:
            return m.group(1).strip().rstrip(".,;- ")
        # Fallback: extract from URL slug (sofiya-{hood}-{type}-offer{id}).
        url_m = re.search(r"sofiya-([a-z\-]+?)-(?:tristaen|kashta|apartament|vila)", url.lower())
        if url_m:
            return url_m.group(1).replace("-", " ").title()
        return None
