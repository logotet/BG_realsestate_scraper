"""imot.bg scraper — the largest Bulgarian real-estate portal."""
from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..constants import PropertyType
from ..logging_setup import get_logger
from .base import BaseScraper, RawListing, SearchConfig
from .registry import register

log = get_logger(__name__)

_BASE = "https://www.imot.bg"

# URL slugs per property type on imot.bg.
_TYPE_SLUGS: dict[PropertyType, str] = {
    PropertyType.APARTMENT_3ROOM: "tristaen",
    PropertyType.HOUSE: "kashta",
}

# imot.bg shows 40 listings per page.
_PER_PAGE = 40

# Regex to pull the source-id from an obiava URL.
_ID_RE = re.compile(r"/obiava-([a-zA-Z0-9]+)-")

# Regex helpers for parsing detail pages.
_AREA_RE = re.compile(r"(\d[\d\s.,]*)\s*(?:кв\.?\s*м|m2|кв\.м\.?|sq\.?\s*m)", re.I)
_PRICE_RE = re.compile(
    r"([\d\s.,]+)\s*(лв\.?|лева|bgn|евро|eur|€|\$|usd)", re.I
)
_FLOOR_RE = re.compile(r"(\d+)\s*[-/]?\s*(?:ри|ти|ви|ми)?\s*ет", re.I)

# Bulgarian month names for date parsing.
_BG_MONTHS: dict[str, int] = {
    "януари": 1, "яну": 1, "февруари": 2, "фев": 2, "март": 3, "мар": 3,
    "април": 4, "апр": 4, "май": 5, "юни": 6, "юли": 7,
    "август": 8, "авг": 8, "септември": 9, "сеп": 9, "октомври": 10, "окт": 10,
    "ноември": 11, "ное": 11, "декември": 12, "дек": 12,
}
_DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_BG_MONTHS) + r")[.,]?\s*(\d{4})",
    re.I,
)


def _abs(url: str) -> str:
    """Ensure a URL is absolute (imot.bg often uses protocol-relative hrefs)."""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return _BASE + url
    return url


def _extract_source_id(url: str) -> str:
    m = _ID_RE.search(url)
    return m.group(1) if m else url


def _parse_date(text: str):
    """Try to extract a date from Bulgarian date string."""
    from datetime import date as _date

    m = _DATE_RE.search(text.lower())
    if not m:
        return None
    day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
    month = _BG_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return _date(year, month, day)
    except ValueError:
        return None


@register
class ImotBgScraper(BaseScraper):
    source = "imot.bg"

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

    # -- Abstract method implementations -----------------------------------

    def iter_list_pages(self, cfg: SearchConfig) -> Iterator[str]:
        slug = cfg.extra["slug"]
        # Page 1: /obiavi/prodazhbi/{slug}/grad-sofiya
        yield f"{_BASE}/obiavi/prodazhbi/{slug}/grad-sofiya"
        # Pages 2+: /obiavi/prodazhbi/grad-sofiya/{slug}/p-{N}
        for page in range(2, self.settings.max_list_pages + 1):
            yield f"{_BASE}/obiavi/prodazhbi/grad-sofiya/{slug}/p-{page}"

    def parse_list_page(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        detail_urls: list[str] = []
        seen: set[str] = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/obiava-" not in href:
                continue
            full = _abs(href)
            if full not in seen:
                seen.add(full)
                detail_urls.append(full)
        log.debug(
            "imot_bg.list_page_parsed",
            url=base_url,
            detail_urls=len(detail_urls),
        )
        return detail_urls

    def parse_detail(self, html: str, url: str, cfg: SearchConfig) -> RawListing:
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        title = self._extract_title(soup)
        price_raw, currency_raw = self._extract_price(soup, text)
        neighborhood_raw = self._extract_neighborhood(soup, text)
        area_sqm = self._extract_area(text)
        furnishing_raw = self._extract_furnishing(text)
        description = self._extract_description(soup)
        images = self._extract_images(soup)
        agency = self._extract_agency(soup)
        posted_at = self._extract_date(text)

        return RawListing(
            source=self.source,
            source_id=_extract_source_id(url),
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
            posted_at=posted_at,
        )

    # -- Private helpers ----------------------------------------------------

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str | None:
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        # Fallback: first large heading
        for tag in ("h2", "h3"):
            el = soup.find(tag)
            if el:
                return el.get_text(strip=True)
        return None

    @staticmethod
    def _extract_price(soup: BeautifulSoup, text: str) -> tuple[str | None, str | None]:
        # Look for EUR price first, then BGN.
        for m in _PRICE_RE.finditer(text):
            amount_str = m.group(1).strip()
            currency_str = m.group(2).strip().lower()
            if currency_str in ("евро", "eur", "€"):
                return amount_str, "EUR"
            if currency_str in ("лв", "лв.", "лева", "bgn"):
                return amount_str, "BGN"
            if currency_str in ("$", "usd"):
                return amount_str, "USD"
        return None, None

    @staticmethod
    def _extract_neighborhood(soup: BeautifulSoup, text: str) -> str | None:
        # imot.bg shows location like "Град София, Лозенец" or "гр. София, Лозенец"
        # The neighborhood is a short label — stop at digits, newlines, or known delimiters.
        loc_re = re.compile(
            r"(?:Град|гр\.?)\s*Софи[яй]\s*[,\-–]\s*"
            r"([A-Za-zА-Яа-яёЁ\s\-\.]+?)"
            r"(?:\s*(?:\d|[,|]|\n)|\s*$)",
            re.I,
        )
        m = loc_re.search(text)
        if m:
            return m.group(1).strip().rstrip(".,;- ")
        # Fallback: check URL-embedded neighborhood from meta or breadcrumbs
        return None

    @staticmethod
    def _extract_area(text: str) -> float | None:
        m = _AREA_RE.search(text)
        if not m:
            return None
        try:
            raw = m.group(1).replace(" ", "").replace(",", ".")
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _extract_furnishing(text: str) -> str | None:
        low = text.lower()
        if "обзаведен" in low:
            if "необзаведен" in low:
                return "необзаведен"
            if "частично обзаведен" in low:
                return "частично обзаведен"
            return "обзаведен"
        if "furnished" in low:
            if "unfurnished" in low:
                return "unfurnished"
            return "furnished"
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # Look for a description block — typically a large text div/p.
        for sel in ("div.description", "div.offer-description", "div#description_div"):
            el = soup.select_one(sel)
            if el:
                return el.get_text(" ", strip=True)[:2000]
        # Fallback: largest <p> or text block.
        paragraphs = soup.find_all("p")
        if paragraphs:
            longest = max(paragraphs, key=lambda p: len(p.get_text(strip=True)))
            txt = longest.get_text(" ", strip=True)
            if len(txt) > 50:
                return txt[:2000]
        return None

    @staticmethod
    def _extract_images(soup: BeautifulSoup) -> list[str]:
        images: list[str] = []
        seen: set[str] = set()
        for img in soup.find_all("img", src=True):
            src = _abs(img["src"])
            if "focus.bg/imot/photo" in src and src not in seen:
                seen.add(src)
                images.append(src)
        return images

    @staticmethod
    def _extract_agency(soup: BeautifulSoup) -> str | None:
        # Agency name often appears near contact info.
        for sel in ("div.agent-name", "span.agent-name", "div.broker-name"):
            el = soup.select_one(sel)
            if el:
                return el.get_text(strip=True)
        # Fallback: look for text patterns.
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            if "/agentsii/" in href or "/agency/" in href:
                txt = a_tag.get_text(strip=True)
                if txt and len(txt) < 200:
                    return txt
        return None

    @staticmethod
    def _extract_date(text: str):
        return _parse_date(text)
