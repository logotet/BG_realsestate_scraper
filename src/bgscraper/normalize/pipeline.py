"""Raw -> normalized listing: canonicalize + filter."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from ..config import Settings
from ..constants import HOUSES_ONLY_NEIGHBORHOODS, DealType, Furnishing, PropertyType
from ..logging_setup import get_logger
from ..scrapers.base import RawListing
from .currency import normalize_price
from .neighborhood import canonicalize
from .pets import refuses_pets
from .property_type import classify

log = get_logger(__name__)

# Property types wanted per deal type; anything else is dropped.
_ALLOWED_TYPES: dict[DealType, set[PropertyType]] = {
    DealType.SALE: {PropertyType.APARTMENT_3ROOM, PropertyType.HOUSE},
    DealType.RENT: {PropertyType.APARTMENT_2ROOM},
}

# Title keywords that mark a listing as the wrong kind of property per deal.
_BAD_TYPES_BY_DEAL: dict[DealType, tuple[str, ...]] = {
    DealType.SALE: ("офис", "парцел", "гараж", "склад", "ателие", "магазин", "хотел",
                    "четиристаен", "петостаен", "двустаен", "едностаен", "сграда"),
    DealType.RENT: ("офис", "парцел", "гараж", "склад", "ателие", "магазин", "хотел",
                    "четиристаен", "петостаен", "тристаен", "едностаен", "многостаен",
                    "мезонет", "къща", "вила", "сграда", "стая под наем", "квартира"),
}


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


def normalize(
    raw: RawListing, settings: Settings, deal_type: DealType = DealType.SALE
) -> NormalizedListing | None:
    """Return a NormalizedListing or None if the listing should be dropped."""

    # Property type: prefer explicit, else classify from raw label.
    prop_type = raw.property_type or classify(raw.property_type_raw)
    if prop_type is None:
        log.debug("normalize.drop.no_property_type", url=raw.url)
        return None
    if prop_type not in _ALLOWED_TYPES[deal_type]:
        log.debug(
            "normalize.drop.wrong_type_for_deal",
            url=raw.url,
            type=prop_type.value,
            deal=deal_type.value,
        )
        return None

    if raw.title:
        title_low = raw.title.lower()
        if any(t in title_low for t in _BAD_TYPES_BY_DEAL[deal_type]):
            log.debug("normalize.drop.wrong_type", url=raw.url, title=raw.title)
            return None
        if "строеж" in title_low:
            log.debug("normalize.drop.in_construction", url=raw.url)
            return None
        _OTHER_CITIES = ("варна", "пловдив", "бургас", "перник", "плевен", "велико търново")
        if any(c in title_low for c in _OTHER_CITIES):
            log.debug("normalize.drop.non_sofia", url=raw.url, title=raw.title)
            return None
        _UI_LABELS = {"нотификации", "локация", "реклама", "категории", "обяви"}
        if title_low in _UI_LABELS:
            log.debug("normalize.drop.ui_label", url=raw.url, title=raw.title)
            return None

    price_eur, currency_code = normalize_price(raw.price_raw, raw.currency_raw)
    if price_eur is None or price_eur <= 0:
        log.debug("normalize.drop.no_price", url=raw.url)
        return None
    if deal_type == DealType.RENT:
        floor = settings.rent_price_min_eur
        cap = settings.rent_price_cap_eur
    else:
        floor = settings.price_min_eur
        cap = (
            settings.price_cap_apartment_eur
            if prop_type == PropertyType.APARTMENT_3ROOM
            else settings.price_cap_house_eur
        )
    if price_eur < floor:
        log.debug("normalize.drop.price_below_min", url=raw.url, price=price_eur, min=floor)
        return None
    if price_eur > cap:
        log.debug("normalize.drop.price_above_cap", url=raw.url, price=price_eur, cap=cap)
        return None

    hood = canonicalize(
        raw.neighborhood_raw, threshold=settings.fuzzy_threshold, deal_type=deal_type
    )
    if hood is None:
        log.debug("normalize.drop.hood_unmatched", url=raw.url, raw=raw.neighborhood_raw)
        return None

    if deal_type == DealType.SALE:
        # в.з. (village zone) neighborhoods allow houses only.
        if hood.lower().startswith("в.з") and prop_type == PropertyType.APARTMENT_3ROOM:
            log.debug("normalize.drop.vz_apartment", url=raw.url, hood=hood)
            return None

        # Specific neighborhoods where only houses are wanted.
        if hood in HOUSES_ONLY_NEIGHBORHOODS and prop_type == PropertyType.APARTMENT_3ROOM:
            log.debug("normalize.drop.houses_only_apartment", url=raw.url, hood=hood)
            return None

        # Minimum apartment size.
        if (
            prop_type == PropertyType.APARTMENT_3ROOM
            and raw.area_sqm is not None
            and raw.area_sqm < 80
        ):
            log.debug("normalize.drop.apartment_too_small", url=raw.url, area=raw.area_sqm)
            return None

    # Rentals must not explicitly refuse pets (no mention at all is fine).
    if deal_type == DealType.RENT and refuses_pets(f"{raw.title or ''} {raw.description or ''}"):
        log.debug("normalize.drop.pets_refused", url=raw.url)
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
