"""Tests for the pet-refusal phrase detector."""
from __future__ import annotations

import pytest

from bgscraper.normalize.pets import refuses_pets

REFUSALS = [
    "Без домашни любимци.",
    "без домашен любимец",
    "Апартаментът се отдава без животни.",
    "Без кучета и котки!",
    "Не се допускат домашни любимци.",
    "Не се приемат наематели с домашни любимци.",
    "не се позволяват животни",
    "Домашни любимци не се допускат.",
    "Домашните любимци не са позволени.",
    "Не приемаме домашни любимци.",
    "Забранено за домашни любимци.",
    "No pets.",
    "Sorry, no animals.",
    "Pets are not allowed.",
    "Not suitable for pets.",
]

NOT_REFUSALS = [
    None,
    "",
    "Светъл двустаен апартамент до метро.",
    "Домашни любимци са добре дошли!",
    "Допускат се домашни любимци.",
    "Разрешени са домашни любимци след уговорка.",
    "Pets allowed.",
    "Pet friendly building.",
    "Апартамент без комисионна.",  # "без" not followed by an animal noun
]


@pytest.mark.parametrize("text", REFUSALS)
def test_refuses_pets_positive(text):
    assert refuses_pets(text) is True


@pytest.mark.parametrize("text", NOT_REFUSALS)
def test_refuses_pets_negative(text):
    assert refuses_pets(text) is False
