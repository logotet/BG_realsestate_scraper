"""Unit tests for the normalization layer."""
from __future__ import annotations

from bgscraper.constants import Furnishing, PropertyType
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


# --- property type ----------------------------------------------------------

def test_classify_apartment():
    assert classify("Тристаен апартамент") == PropertyType.APARTMENT_3ROOM


def test_classify_house():
    assert classify("Къща в София") == PropertyType.HOUSE


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
