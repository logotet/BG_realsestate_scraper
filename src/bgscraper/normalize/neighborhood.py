"""Canonicalize raw neighborhood strings to the fixed NEIGHBORHOODS list."""
from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from ..constants import NEIGHBORHOOD_ALIASES, NEIGHBORHOODS

_PREFIX_NOISE = re.compile(
    r"^(гр\.?|град|софия|sofia|район|кв\.?|квартал|бул\.?|ул\.?|м-т|вилна зона|в\.з\.?|ж\.гр\.?)\s*",
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


def canonicalize(raw: str | None, threshold: int = 80) -> str | None:
    if not raw:
        return None
    # Try the raw string against the alias map first (match against cleaned key).
    cleaned = _clean(raw)
    if cleaned in NEIGHBORHOOD_ALIASES:
        return NEIGHBORHOOD_ALIASES[cleaned]

    # Substring shortcut: canonical name appears inside the raw text.
    low_raw = raw.lower()
    for canon in NEIGHBORHOODS:
        if canon.lower() in low_raw:
            return canon

    # Fuzzy match against canonicals (using the cleaned form).
    match = process.extractOne(
        cleaned or raw.lower(),
        [n.lower() for n in NEIGHBORHOODS],
        scorer=fuzz.WRatio,
    )
    if match is None:
        return None
    _, score, idx = match
    if score < threshold:
        return None
    return NEIGHBORHOODS[idx]
