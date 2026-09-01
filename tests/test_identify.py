"""Nobody gets a booking recorded against them until we know who they are.

The live bug: someone opened another lead's deep link, said "I am not anita",
and the agent qualified them, showed listings and booked a site visit - all
attributed to Anita Rao.
"""
from dataclasses import dataclass, field

import pytest

from app.domain import stages
from app.domain.slots import looks_like_name, parse_phone
from app.llm.extract import Extraction
from tests.test_stages import CATALOG


@dataclass
class State:
    stage: str = stages.NEW
    slots: dict = field(default_factory=dict)
    selected_property_id: str | None = None
    opted_out: bool = False

    @property
    def property_type(self): return self.slots.get("property_type")
    @property
    def budget(self): return self.slots.get("budget")
    @property
    def area(self): return self.slots.get("area")
    @property
    def qualified(self): return bool(self.property_type and self.budget and self.area)


def ex(intent="other", **kw):
    return Extraction(intent=intent, language=kw.pop("language", "en"), **kw)


def test_denying_identity_starts_a_new_lead():
    plan = stages.decide(State(stage=stages.GREETED), ex("not_the_lead"), CATALOG, [])
    assert plan.stage == stages.IDENTIFYING
    assert plan.new_lead is True, "must detach from the lead in the deep link"
    assert "name" in plan.instruction and "mobile" in plan.instruction


def test_nothing_is_shown_before_identification():
    """The bug: it went straight into qualifying and listing for a stranger."""
    state = State(stage=stages.IDENTIFYING)
    plan = stages.decide(state, ex("gave_requirements", property_type="3BHK",
                                   budget=20_000_000, area="Whitefield"),
                         CATALOG, [])
    assert plan.stage == stages.IDENTIFYING
    assert not plan.shown, "no listings until we know who they are"


def test_name_only_then_asks_for_number():
    plan = stages.decide(State(stage=stages.IDENTIFYING),
                         ex("gave_contact", person_name="Sayeed"), CATALOG, [])
    assert plan.stage == stages.IDENTIFYING
    assert plan.capture_name == "Sayeed"
    assert "mobile number" in plan.instruction


def test_number_only_then_asks_for_name():
    plan = stages.decide(State(stage=stages.IDENTIFYING),
                         ex("gave_contact", phone="+919980201901"), CATALOG, [])
    assert plan.capture_phone == "+919980201901"
    assert "name" in plan.instruction


def test_both_captured_moves_on_to_qualifying():
    state = State(stage=stages.IDENTIFYING, slots={"captured_name": "Sayeed"})
    plan = stages.decide(state, ex("gave_contact", phone="9980201901"), CATALOG, [])
    assert plan.stage == stages.QUALIFYING
    assert plan.capture_name == "Sayeed"
    assert plan.capture_phone == "+919980201901"


def test_booking_cannot_happen_while_identifying():
    state = State(stage=stages.IDENTIFYING)
    plan = stages.decide(state, ex("gave_slot", slot_text="Saturday 11am"), CATALOG, CATALOG)
    assert plan.stage == stages.IDENTIFYING
    assert plan.booking_slot_text is None, "never book for an unidentified person"


@pytest.mark.parametrize("raw,expected", [
    ("9980201901", "+919980201901"),
    ("+91 99802 01901", "+919980201901"),
    ("09980201901", "+919980201901"),
])
def test_phone_normalised(raw, expected):
    assert parse_phone(raw) == expected


@pytest.mark.parametrize("bad", ["1234567890", "20000000", "2 cr", ""])
def test_non_phones_rejected(bad):
    """A budget figure must never be stored as a phone number."""
    assert parse_phone(bad) is None


@pytest.mark.parametrize("text,ok", [
    ("Sayeed", True), ("Md Sayeed", True), ("R. Kumar", True),
    ("9980201901", False), ("A", False),
])
def test_name_plausibility(text, ok):
    assert looks_like_name(text) is ok
