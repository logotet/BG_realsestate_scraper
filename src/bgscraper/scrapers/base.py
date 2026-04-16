"""BaseScraper and the RawListing / SearchConfig dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

from ..config import Settings
from ..constants import PropertyType
from ..logging_setup import get_logger
from .http import HttpClient

log = get_logger(__name__)


@dataclass
class RawListing:
    """Untransformed listing as pulled directly from a site."""

    source: str
    source_id: str
    url: str
    title: str | None = None
    price_raw: str | None = None
    currency_raw: str | None = None
    property_type_raw: str | None = None
    property_type: PropertyType | None = None
    neighborhood_raw: str | None = None
    area_sqm: float | None = None
    furnishing_raw: str | None = None
    description: str | None = None
    images: list[str] = field(default_factory=list)
    agency: str | None = None
    posted_at: date | None = None


@dataclass
class SearchConfig:
    property_type: PropertyType
    price_cap_eur: int
    # Free-form extra fields per site (e.g. a search URL template).
    extra: dict[str, object] = field(default_factory=dict)


class BaseScraper(ABC):
    """Subclass contract:

    - ``source``: canonical source name stored in the DB.
    - ``search_configs``: one per (property_type, price_cap) to iterate.
    - ``iter_list_pages``: yields list-page URLs (pagination) for a config.
    - ``parse_list_page``: list-page HTML -> detail URLs.
    - ``parse_detail``: detail-page HTML -> RawListing.
    """

    source: str

    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings
        self.search_configs: list[SearchConfig] = self._build_search_configs()

    def _build_search_configs(self) -> list[SearchConfig]:
        return [
            SearchConfig(PropertyType.APARTMENT_3ROOM, self.settings.price_cap_apartment_eur),
            SearchConfig(PropertyType.HOUSE, self.settings.price_cap_house_eur),
        ]

    @abstractmethod
    def iter_list_pages(self, cfg: SearchConfig) -> Iterator[str]: ...

    @abstractmethod
    def parse_list_page(self, html: str, base_url: str) -> list[str]: ...

    @abstractmethod
    def parse_detail(self, html: str, url: str, cfg: SearchConfig) -> RawListing: ...

    def run(self) -> list[RawListing]:
        results: list[RawListing] = []
        for cfg in self.search_configs:
            fail = ok = 0
            consecutive_list_fails = 0
            for list_url in self.iter_list_pages(cfg):
                try:
                    list_html = self.http.get(list_url)
                    consecutive_list_fails = 0
                except Exception as e:
                    consecutive_list_fails += 1
                    log.warning(
                        "scraper.list_page_failed",
                        source=self.source,
                        url=list_url,
                        error=str(e),
                    )
                    if consecutive_list_fails >= 3:
                        log.error(
                            "scraper.list_pages_unreachable",
                            source=self.source,
                            consecutive_fails=consecutive_list_fails,
                        )
                        break
                    continue
                detail_urls = self.parse_list_page(list_html, list_url)
                if not detail_urls:
                    break  # empty page → stop paginating
                for detail_url in detail_urls:
                    try:
                        d_html = self.http.get(detail_url, referer=list_url)
                        raw = self.parse_detail(d_html, detail_url, cfg)
                        results.append(raw)
                        ok += 1
                    except Exception as e:
                        fail += 1
                        log.warning(
                            "scraper.detail_failed",
                            source=self.source,
                            url=detail_url,
                            error=str(e),
                        )
                # circuit breaker: > 50% failures after at least 10 attempts
                if ok + fail >= 10 and fail / (ok + fail) > 0.5:
                    log.error(
                        "scraper.circuit_breaker_tripped",
                        source=self.source,
                        ok=ok,
                        fail=fail,
                    )
                    return results
        return results
