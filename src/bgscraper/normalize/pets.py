"""Detect explicit pet-refusal phrases in rental ad text.

Patterns are refusal-anchored (a negation word adjacent to the animal noun),
so bare mentions like "домашни любимци са добре дошли" or "pet friendly"
never match. Listings that don't mention pets at all are kept.
"""
from __future__ import annotations

import re

# Animal noun variants: "домашни любимци", "животни", "кучета", "котки", ...
_ANIMALS = r"(?:домашни\s+)?(?:любимци|животни|кучета?|котки?)"

_PETS_REFUSED_RES = [
    # "без домашни любимци", "без животни", "без кучета и котки"
    re.compile(rf"\bбез\s+{_ANIMALS}", re.I),
    re.compile(r"\bбез\s+домашен\s+любимец", re.I),
    # "не се допускат (наематели с) домашни любимци" — bounded gap covers
    # intervening words like "наематели с".
    re.compile(
        rf"\bне\s+се\s+(?:допускат|приемат|позволяват|разрешават|толерират)"
        rf"(?:\s+\S+){{0,3}}?\s+{_ANIMALS}",
        re.I,
    ),
    # "домашни любимци не се допускат / не са позволени"
    re.compile(
        rf"{_ANIMALS}\s+не\s+(?:се\s+(?:допускат|приемат|позволяват|разрешават)"
        rf"|са\s+(?:позволени|разрешени|допустими|желани))",
        re.I,
    ),
    # "не приемаме/допускаме домашни любимци"
    re.compile(
        rf"\bне\s+(?:приемаме|допускаме|позволяваме|разрешаваме)\s+{_ANIMALS}", re.I
    ),
    # "забранено за домашни любимци", "забранени са домашни любимци"
    re.compile(rf"\bзабранен[иоае]?\s+(?:са\s+|е\s+)?(?:за\s+)?{_ANIMALS}", re.I),
    # English variants
    re.compile(r"\bno\s+pets\b", re.I),
    re.compile(r"\bno\s+animals\b", re.I),
    re.compile(r"\bpets?\s+(?:are\s+)?not\s+(?:allowed|permitted|accepted|welcome)\b", re.I),
    re.compile(r"\bnot\s+suitable\s+for\s+pets\b", re.I),
]


def refuses_pets(text: str | None) -> bool:
    """True if the text explicitly refuses pets; no mention -> False."""
    if not text:
        return False
    return any(rx.search(text) for rx in _PETS_REFUSED_RES)
