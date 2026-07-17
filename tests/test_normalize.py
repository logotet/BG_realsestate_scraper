"""Unit tests for the normalization layer."""
from __future__ import annotations

from bgscraper.constants import DealType, Furnishing, PropertyType
from bgscraper.normalize.currency import normalize_price, parse_amount
from bgscraper.normalize.neighborhood import canonicalize
from bgscraper.normalize.pipeline import normalize
from bgscraper.normalize.property_type import classify
from bgscraper.scrapers.base import RawListing


# --- currency ---------------------------------------------------------------

def test_parse_amount_handles_spaces_and_commas():
    assert parse_amount("299 000") == 299000
    assert parse_amount("299,000") == 299000
    assert parse_amount("299.000,50") == 299000.5
    assert parse_amount("199,999.99") == 199999.99
    assert parse_amount(None) is None
    assert parse_amount("") is None


def test_normalize_price_eur_passthrough():
    price, code = normalize_price("299 000 EUR", "EUR")
    assert price == 299000
    assert code == "EUR"


def test_normalize_price_bgn_to_eur():
    price, code = normalize_price("600 000 лв", "лв")
    # 600_000 / 1.95583 ≈ 306_775
    assert 306_000 <= price <= 307_500
    assert code == "BGN"


# --- neighborhood -----------------------------------------------------------

def test_canonicalize_exact_substring():
    assert canonicalize("София, Лозенец, ул. Златовръх") == "Лозенец"


def test_canonicalize_alias():
    assert canonicalize("Манастирски ливади - запад") == "Манастирски ливади"


def test_canonicalize_fuzzy():
    assert canonicalize("Красно Село, близо до парка") == "Красно село"


def test_canonicalize_miss():
    assert canonicalize("Люлин 5") is None


def test_canonicalize_gorna_banya():
    assert canonicalize("София, Горна баня") == "Горна Баня"


def test_canonicalize_gorna_banya_vz_variant_wins():
    # The village-zone variant is listed first so в.з. listings stay houses-only.
    assert canonicalize("в.з. Горна Баня") == "в.з. Горна Баня"


def test_canonicalize_german():
    assert canonicalize("София, с. Герман") == "Герман"


def test_canonicalize_lozen():
    assert canonicalize("с. Лозен") == "Лозен"


def test_canonicalize_gorni_lozen():
    assert canonicalize("Горни Лозен") == "Лозен"


def test_canonicalize_lozenets_not_shadowed_by_lozen():
    # "Лозен" is a substring of "Лозенец"; Лозенец must keep matching itself.
    assert canonicalize("Лозенец") == "Лозенец"


# --- property type ----------------------------------------------------------

def test_classify_apartment():
    assert classify("Тристаен апартамент") == PropertyType.APARTMENT_3ROOM


def test_classify_house():
    assert classify("Къща в София") == PropertyType.HOUSE


def test_classify_two_room():
    assert classify("Двустаен апартамент") == PropertyType.APARTMENT_2ROOM
    assert classify("dvustaen") is None  # slug alone isn't a recognized label


# --- full pipeline ----------------------------------------------------------

def test_normalize_drops_above_price_cap(settings):
    raw = RawListing(
        source="imot.bg",
        source_id="1",
        url="https://imot.bg/x",
        title="Тристаен",
        price_raw="500 000 EUR",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_3ROOM,
        neighborhood_raw="Лозенец",
    )
    assert normalize(raw, settings) is None


def test_normalize_drops_unknown_neighborhood(settings):
    raw = RawListing(
        source="imot.bg",
        source_id="1",
        url="https://imot.bg/x",
        price_raw="200 000 EUR",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_3ROOM,
        neighborhood_raw="Люлин 5",
    )
    assert normalize(raw, settings) is None


def test_normalize_drops_apartment_in_houses_only_village(settings):
    raw = RawListing(
        source="imot.bg",
        source_id="1",
        url="https://imot.bg/x",
        title="Тристаен",
        price_raw="200 000 EUR",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_3ROOM,
        neighborhood_raw="с. Лозен",
        area_sqm=95.0,
    )
    assert normalize(raw, settings) is None


def test_normalize_happy_path(settings):
    raw = RawListing(
        source="imot.bg",
        source_id="42",
        url="https://imot.bg/42",
        title="Тристаен в Лозенец",
        price_raw="299 000 EUR",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_3ROOM,
        neighborhood_raw="София, Лозенец",
        area_sqm=95.0,
        furnishing_raw="Напълно обзаведен",
        description="Луксозен апартамент",
        images=["https://img/1.jpg"],
    )
    out = normalize(raw, settings)
    assert out is not None
    assert out.price_eur == 299_000
    assert out.neighborhood == "Лозенец"
    assert out.property_type == PropertyType.APARTMENT_3ROOM
    assert out.furnishing == Furnishing.FURNISHED
    assert "img/1.jpg" in out.images_json


# --- rent pipeline ----------------------------------------------------------

def _rent_raw(**overrides):
    base = dict(
        source="imot.bg",
        source_id="7",
        url="https://imot.bg/7",
        title="Двустаен апартамент в Лозенец",
        price_raw="550 €/месец",
        currency_raw="EUR",
        property_type=PropertyType.APARTMENT_2ROOM,
        neighborhood_raw="София, Лозенец",
        area_sqm=62.0,
        description="Светъл апартамент до метростанция.",
    )
    base.update(overrides)
    return RawListing(**base)


def test_normalize_rent_happy_path(settings):
    out = normalize(_rent_raw(), settings, DealType.RENT)
    assert out is not None
    assert out.price_eur == 550
    assert out.property_type == PropertyType.APARTMENT_2ROOM
    assert out.neighborhood == "Лозенец"


def test_normalize_rent_price_monthly_bgn(settings):
    out = normalize(_rent_raw(price_raw="1 100 лв./месец", currency_raw=None), settings,
                    DealType.RENT)
    assert out is not None
    assert 555 <= out.price_eur <= 570  # 1100 / 1.95583 ≈ 562


def test_normalize_rent_price_band(settings):
    assert normalize(_rent_raw(price_raw="400 EUR"), settings, DealType.RENT) is None
    assert normalize(_rent_raw(price_raw="750 EUR"), settings, DealType.RENT) is None
    assert normalize(_rent_raw(price_raw="450 EUR"), settings, DealType.RENT) is not None
    assert normalize(_rent_raw(price_raw="700 EUR"), settings, DealType.RENT) is not None


def test_normalize_rent_drops_wrong_titles(settings):
    for title in ("Тристаен под наем", "Къща в Бояна", "Стая под наем в Лозенец"):
        assert normalize(_rent_raw(title=title), settings, DealType.RENT) is None


def test_normalize_rent_drops_wrong_property_type(settings):
    raw = _rent_raw(property_type=PropertyType.APARTMENT_3ROOM, title="Апартамент")
    assert normalize(raw, settings, DealType.RENT) is None


def test_normalize_sale_drops_two_room(settings):
    """Regression guard: sale search must never keep a 2-room apartment."""
    raw = _rent_raw(price_raw="200 000 EUR", title="Апартамент в Лозенец")
    assert normalize(raw, settings) is None


def test_normalize_rent_skips_sale_only_rules(settings):
    # Small area, houses-only neighborhood, and в.з. zone are all fine for rent.
    assert normalize(
        _rent_raw(area_sqm=45.0, neighborhood_raw="кв. Герман",
                  title="Двустаен в Герман"),
        settings, DealType.RENT,
    ) is not None
    assert normalize(
        _rent_raw(neighborhood_raw="в.з. Бояна", title="Двустаен в Бояна"),
        settings, DealType.RENT,
    ) is not None


def test_normalize_rent_drops_pets_refused_in_description(settings):
    raw = _rent_raw(description="Апартаментът се отдава без домашни любимци.")
    assert normalize(raw, settings, DealType.RENT) is None


def test_normalize_rent_drops_pets_refused_in_title(settings):
    raw = _rent_raw(title="Двустаен в Лозенец - no pets")
    assert normalize(raw, settings, DealType.RENT) is None


def test_normalize_rent_keeps_pets_welcome(settings):
    raw = _rent_raw(description="Домашни любимци са добре дошли!")
    assert normalize(raw, settings, DealType.RENT) is not None
