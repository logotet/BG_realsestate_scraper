"""Fixed search constants: target neighborhoods and property-type labels."""
from __future__ import annotations

from enum import Enum


class PropertyType(str, Enum):
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
    "Косанин дол",
]

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
}

SOFIA_CITY_NAMES = {"софия", "sofia", "гр. софия", "гр.софия"}

# Currency pegs / fallback rates used when source currency isn't EUR.
BGN_TO_EUR = 1 / 1.95583  # BGN is pegged to EUR
USD_TO_EUR_FALLBACK = 0.92  # fallback when no live rate is available
