"""Raw -> normalized listing: canonicalize + filter."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..config import Settings
from ..constants import Furnishing, PropertyType
from ..logging_setup import get_logger
from ..scrapers.base import RawListing
from .currency import normalize_price
from .neighborhood import canonicalize
from .property_type import classify

log = get_logger(__name__)


@dataclass
class NormalizedListing:
    source: str
    source_id: str
    url: str
    title: str | None
    price_eur: int
    price_raw: str | None
    currency_raw: str | None
    property_type: PropertyType
    neighborhood: str
    neighborhood_raw: str | None
    area_sqm: float | None
    furnishing: Furnishing
    description: str | None
    images_json: str
    agency: str | None
    posted_at: date | None


_FURNISHING_MAP = {
    "обзаведен": Furnishing.FURNISHED,
    "напълно обзаведен": Furnishing.FURNISHED,
    "furnished": Furnishing.FURNISHED,
    "необзаведен": Furnishing.UNFURNISHED,
    "unfurnished": Furnishing.UNFURNISHED,
    "частично": Furnishing.PARTIAL,
    "частично обзаведен": Furnishing.PARTIAL,
    "partially furnished": Furnishing.PARTIAL,
}


def _classify_furnishing(raw: str | None) -> Furnishing:
    if not raw:
        return Furnishing.UNKNOWN
    low = raw.lower()
    for token, val in _FURNISHING_MAP.items():
        if token in low:
            return val
    return Furnishing.UNKNOWN


def normalize(raw: RawListing, settings: Settings) -> NormalizedListing | None:
    """Return a NormalizedListing or None if the listing should be dropped."""

    # Property type: prefer explicit, else classify from raw label.
    prop_type = raw.property_type or classify(raw.property_type_raw)
    if prop_type is None:
        log.debug("normalize.drop.no_property_type", url=raw.url)
        return None

    price_eur, currency_code = normalize_price(raw.price_raw, raw.currency_raw)
    if price_eur is None or price_eur <= 0:
        log.debug("normalize.drop.no_price", url=raw.url)
        return None

    cap = (
        settings.price_cap_apartment_eur
        if prop_type == PropertyType.APARTMENT_3ROOM
        else settings.price_cap_house_eur
    )
    if price_eur > cap:
        log.debug("normalize.drop.price_above_cap", url=raw.url, price=price_eur, cap=cap)
        return None

    hood = canonicalize(raw.neighborhood_raw, threshold=settings.fuzzy_threshold)
    if hood is None:
        log.debug("normalize.drop.hood_unmatched", url=raw.url, raw=raw.neighborhood_raw)
        return None

    furnishing = _classify_furnishing(raw.furnishing_raw)
    images_json = json.dumps(raw.images or [], ensure_ascii=False)

    return NormalizedListing(
        source=raw.source,
        source_id=raw.source_id,
        url=raw.url,
        title=raw.title,
        price_eur=price_eur,
        price_raw=raw.price_raw,
        currency_raw=currency_code or raw.currency_raw,
        property_type=prop_type,
        neighborhood=hood,
        neighborhood_raw=raw.neighborhood_raw,
        area_sqm=raw.area_sqm,
        furnishing=furnishing,
        description=raw.description,
        images_json=images_json,
        agency=raw.agency,
        posted_at=raw.posted_at,
    )
