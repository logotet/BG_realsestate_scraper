"""Raw property-type labels -> canonical PropertyType enum."""
from __future__ import annotations

from ..constants import PropertyType

_APT_2_TOKENS = (
    "двустаен",
    "2-стаен",
    "2 стаен",
    # Bulgarian "двустаен" = living room + 1 bedroom, i.e. one-bedroom in EN terms.
    "one-bedroom",
    "1-bedroom",
    "1 bedroom",
    "two-room",
    "2-room",
)
_APT_3_TOKENS = (
    "тристаен",
    "3-стаен",
    "3 стаен",
    "three-bedroom",
    "3-bedroom",
    "3 bedroom",
    "3-room",
)
_HOUSE_TOKENS = (
    "къща",
    "house",
    "вила",
    "villa",
    "мезонет",  # split-level but typically marketed as house-style
)


def classify(raw: str | None) -> PropertyType | None:
    if not raw:
        return None
    t = raw.lower()
    if any(tok in t for tok in _APT_3_TOKENS):
        return PropertyType.APARTMENT_3ROOM
    if any(tok in t for tok in _APT_2_TOKENS):
        return PropertyType.APARTMENT_2ROOM
    if any(tok in t for tok in _HOUSE_TOKENS):
        return PropertyType.HOUSE
    return None
