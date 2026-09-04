"""Fixed search constants: target neighborhoods and property-type labels."""
from __future__ import annotations

from enum import Enum


class DealType(str, Enum):
    SALE = "sale"
    RENT = "rent"


class PropertyType(str, Enum):
    APARTMENT_2ROOM = "apartment_2room"
    APARTMENT_3ROOM = "apartment_3room"
    HOUSE = "house"


class Furnishing(str, Enum):
    FURNISHED = "furnished"
    UNFURNISHED = "unfurnished"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


# Canonical neighborhood names (as provided by user).
NEIGHBORHOODS: list[str] = [
    "Лозенец",
    "Манастирски ливади",
    "Витоша",
    "Борово",
    "Бояна",
    "Драгалевци",
    "Гоце Делчев",
    "Кръстова вада",
    "Стрелбище",
    "Белите брези",
    "Бъкстон",
    "Павлово",
    "Лагера",
    "Симеоново",
    "Красно село",
    "Хиподрума",
    "Иван Вазов",
    "Хладилника",
    "м-т Гърдова глава",
    "ж.гр. Южен парк",
    "в.з. Симеоново - Драгалевци",
    "в.з. Беловодски път",
    "в.з. Бояна",
    "Градина",
    "в.з Малинова Долина",
    "в.з. Бункера",
    "Бистрица",
    "Железница",
    "в.з. Косанин дол",
    "в.з. Горна Баня",
    "Горна Баня",
    "в.з. Панчарево",
    "в.з. Хераково",
    "в.з. Костинброд",
    "в.з. Божурище",
    "в.з. Кокаляне",
    "Герман",
    "Лозен",
]

# Neighborhoods outside в.з. zones where only houses are wanted.
HOUSES_ONLY_NEIGHBORHOODS = {"Манастирски ливади", "Герман", "Лозен"}

# Extra neighborhoods searched for rentals only (not part of the sale universe).
RENT_ONLY_NEIGHBORHOODS: list[str] = [
    "Дианабад",
    "Гео Милев",
    "Изток",
]

# Active canonical neighborhood set per deal type. Rent-only names come last so the
# ordered substring match in normalize/neighborhood.py still prefers longer canonicals.
NEIGHBORHOODS_BY_DEAL: dict[DealType, list[str]] = {
    DealType.SALE: NEIGHBORHOODS,
    DealType.RENT: NEIGHBORHOODS + RENT_ONLY_NEIGHBORHOODS,
}

# Common aliases / alternate spellings mapped to canonical form.
# Add more as real scraped data reveals variants.
NEIGHBORHOOD_ALIASES: dict[str, str] = {
    "манастирски ливади - запад": "Манастирски ливади",
    "манастирски ливади - изток": "Манастирски ливади",
    "манастирски ливади запад": "Манастирски ливади",
    "манастирски ливади изток": "Манастирски ливади",
    "гоце делчев": "Гоце Делчев",
    "кръстова вада": "Кръстова вада",
    "южен парк": "ж.гр. Южен парк",
    "гърдова глава": "м-т Гърдова глава",
    "бояна": "Бояна",
    "беловодски път": "в.з. Беловодски път",
    "симеоново-драгалевци": "в.з. Симеоново - Драгалевци",
    "симеоново - драгалевци": "в.з. Симеоново - Драгалевци",
    "бункера": "в.з. Бункера",
    "панчарево": "в.з. Панчарево",
    "панчерево": "в.з. Панчарево",
    "хераково": "в.з. Хераково",
    "костинброд": "в.з. Костинброд",
    "божурище": "в.з. Божурище",
    "кокаляне": "в.з. Кокаляне",
    "косанин дол": "в.з. Косанин дол",
    # Pin Малинова долина before the rent-only "Изток" can fuzzy-steal it.
    "малинова долина": "в.з Малинова Долина",
    "малинова долина изток": "в.з Малинова Долина",
    "малинова долина запад": "в.з Малинова Долина",
}

SOFIA_CITY_NAMES = {"софия", "sofia", "гр. софия", "гр.софия"}

# Currency pegs / fallback rates used when source currency isn't EUR.
BGN_TO_EUR = 1 / 1.95583  # BGN is pegged to EUR
USD_TO_EUR_FALLBACK = 0.92  # fallback when no live rate is available
