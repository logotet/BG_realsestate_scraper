"""Canonicalize raw neighborhood strings to the fixed per-deal neighborhood set."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from ..constants import NEIGHBORHOOD_ALIASES, NEIGHBORHOODS_BY_DEAL, DealType

_PREFIX_NOISE = re.compile(
    r"^(гр\.?|град|софия|sofia|район|кв\.?|квартал|бул\.?|ул\.?|м-т|вилна зона|в\.з\.?|ж\.гр\.?"
    r"|офис|апартамент|тристаен|двустаен|едностаен|парцел|гараж|склад|магазин|вила|хотел)\s*",
    flags=re.IGNORECASE,
)


def _clean(text: str) -> str:
    t = text.strip().lower()
    # Strip known prefixes that don't help matching.
    prev = None
    while prev != t:
        prev = t
        t = _PREFIX_NOISE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip(" ,-")
    return t


def canonicalize(
    raw: str | None,
    threshold: int = 80,
    deal_type: DealType = DealType.SALE,
) -> str | None:
    if not raw:
        return None
    names = NEIGHBORHOODS_BY_DEAL[deal_type]

    # Try the raw string against the alias map first (match against cleaned key).
    cleaned = _clean(raw)
    alias = NEIGHBORHOOD_ALIASES.get(cleaned)
    if alias is not None:
        # An alias may point at a name outside this deal's universe (e.g. rent-only).
        return alias if alias in names else None

    # Substring shortcut: canonical name appears inside the raw text.
    low_raw = raw.lower()
    for canon in names:
        if canon.lower() in low_raw:
            return canon

    # Fuzzy match against canonicals (using the cleaned form).
    # Strip trailing numbers so "младост 3" doesn't anchor to "киноцентъра 3 ч".
    cleaned_for_fuzzy = re.sub(r"\s+\d+\s*$", "", cleaned or raw.lower()).strip()
    match = process.extractOne(
        cleaned_for_fuzzy or cleaned or raw.lower(),
        [n.lower() for n in names],
        scorer=fuzz.WRatio,
    )
    if match is None:
        return None
    _, score, idx = match
    if score < threshold:
        return None
    return names[idx]
