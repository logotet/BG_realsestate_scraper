"""Price + currency normalization to EUR (integer)."""
from __future__ import annotations

import re

from ..constants import BGN_TO_EUR, USD_TO_EUR_FALLBACK

_NON_DIGITS = re.compile(r"[^\d,.\s]")
_WHITESPACE = re.compile(r"\s+")

_CURRENCY_TOKENS = {
    "eur": "EUR",
    "евро": "EUR",
    "€": "EUR",
    "bgn": "BGN",
    "лв": "BGN",
    "лв.": "BGN",
    "лева": "BGN",
    "usd": "USD",
    "$": "USD",
}


def detect_currency(text: str | None) -> str | None:
    if not text:
        return None
    t = text.strip().lower()
    for token, code in _CURRENCY_TOKENS.items():
        if token in t:
            return code
    return None


def parse_amount(text: str | None) -> float | None:
    if not text:
        return None
    t = _NON_DIGITS.sub("", text)
    t = _WHITESPACE.sub("", t)
    if not t:
        return None
    # Handle thousands separators: if both , and . exist, last one is decimal.
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        # Ambiguous: treat comma as thousands separator if 3-digit groups.
        parts = t.split(",")
        if all(len(p) == 3 for p in parts[1:]):
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def to_eur(amount: float | None, currency: str | None) -> int | None:
    if amount is None:
        return None
    code = (currency or "EUR").upper()
    if code == "EUR":
        return int(round(amount))
    if code == "BGN":
        return int(round(amount * BGN_TO_EUR))
    if code == "USD":
        return int(round(amount * USD_TO_EUR_FALLBACK))
    return None


def normalize_price(price_raw: str | None, currency_raw: str | None) -> tuple[int | None, str | None]:
    """Return (price_eur, currency_code) from raw text pieces."""
    detected = detect_currency(currency_raw) or detect_currency(price_raw)
    amount = parse_amount(price_raw)
    return to_eur(amount, detected), detected
