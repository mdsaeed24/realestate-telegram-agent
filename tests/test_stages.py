"""The stage machine is pure, so the brief's rules can be tested directly."""
from dataclasses import dataclass, field

from app.domain import stages
from app.llm.extract import Extraction
from app.sheets.properties import Property


def prop(pid, name, ptype, price, locality, media="", video=""):
    return Property(
        property_id=pid, name=name, property_type=ptype, price_inr=price,
        locality=locality, city="Bengaluru", status="active",
        key_details="Ready to move\n1650 sq ft", maps_url="https://maps/x",
        media_folder=media, hero_file="Hero.png" if media else "",
        gallery_files=["Image 1.png", "Image 2.png"] if media else [],
        video_file=video,
    )


WITH_MEDIA = prop("PROP-001", "Sobha Magnolia", "3BHK", 20_000_000,
                  "Bengaluru-Mysuru Expressway", media="Sobha Magnolia")
NO_MEDIA = prop("PROP-004", "Riverbend Residences", "3BHK", 18_500_000,
                "Bengaluru-Mysuru Expressway")
CATALOG = [WITH_MEDIA, NO_MEDIA,
           prop("PROP-003", "Green Meadows", "2BHK", 13_500_000, "Varthur")]


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


QUALIFIED = {"property_type": "3BHK", "budget": 20_000_000, "area": "Bengaluru-Mysuru Expressway"}


# --- the "no" path --------------------------------------------------------

def test_not_looking_ends_gracefully_and_opts_out():
    plan = stages.decide(State(stage=stages.GREETED), ex("not_looking"), CATALOG, [])
    assert plan.stage == stages.NOT_LOOKING
    assert plan.opted_out is True


def test_opted_out_lead_is_never_messaged_again():
    """NOT_LOOKING is absorbing - no further message, whatever they send."""
    plan = stages.decide(State(stage=stages.NOT_LOOKING, opted_out=True),
                         ex("still_looking"), CATALOG, [])
    assert plan.silent is True


# --- qualification --------------------------------------------------------

def test_still_looking_asks_the_three_questions():
    plan = stages.decide(State(stage=stages.GREETED), ex("still_looking"), CATALOG, [])
    assert plan.stage == stages.QUALIFYING
    for want in ("kind of property", "budget", "area"):
        assert want in plan.instruction


def test_partial_requirements_ask_only_for_what_is_missing():
    state = State(stage=stages.QUALIFYING, slots={"property_type": "3BHK"})
    plan = stages.decide(state, ex("gave_requirements", budget=20_000_000), CATALOG, [])
    assert "which area" in plan.instruction
    assert "what budget" not in plan.instruction, "do not re-ask what they just told us"


def test_full_requirements_produce_a_numbered_list():
    plan = stages.decide(State(stage=stages.QUALIFYING),
                         ex("gave_requirements", property_type="3BHK",
                            budget=20_000_000, area="Bengaluru-Mysuru Expressway"),
                         CATALOG, [])
    assert plan.stage == stages.LISTED
    assert plan.facts.startswith("1. ")
    assert plan.shown


# --- no match -------------------------------------------------------------

def test_no_match_is_honest_and_does_not_push():
    plan = stages.decide(State(stage=stages.QUALIFYING),
                         ex("gave_requirements", property_type="3BHK",
                            budget=5_000_000, area="Koramangala"),
                         CATALOG, [])
    assert "honestly" in plan.instruction
    assert "do not push" in plan.instruction.lower()
    assert plan.shown, "offer alternatives rather than a dead end"


# --- picking a property ---------------------------------------------------

def test_picking_by_number_sends_details_and_hero_only():
    state = State(stage=stages.LISTED, slots=QUALIFIED)
    plan = stages.decide(state, ex("picked_property", reply_reference="1"), CATALOG, CATALOG)
    assert plan.stage == stages.PROPERTY_SELECTED
    assert plan.send_hero is WITH_MEDIA
    assert plan.send_gallery is None, "hero alone first - the rest needs consent"


def test_property_without_media_answers_in_text():
    """A listing with no media is normal behaviour, not an error."""
    state = State(stage=stages.LISTED, slots=QUALIFIED)
    plan = stages.decide(state, ex("picked_property", reply_reference="2"), CATALOG, CATALOG)
    assert plan.send_hero is None
    assert "not up yet" in plan.instruction
    assert "site visit" in plan.instruction


def test_unknown_property_is_refused_not_invented():
    state = State(stage=stages.LISTED, slots=QUALIFIED)
    plan = stages.decide(state, ex("picked_property", reply_reference="9"), CATALOG, CATALOG)
    assert plan.send_hero is None
    assert "do not have" in plan.instruction.lower()
    assert "invent" in plan.instruction.lower()


def test_typo_asks_for_confirmation_before_sending():
    state = State(stage=stages.LISTED, slots=QUALIFIED)
    plan = stages.decide(state, ex("picked_property", reply_reference="sobha magnolea"),
                         CATALOG, CATALOG)
    assert plan.send_hero is None, "confirm before sending anything"
    assert "whether they meant" in plan.instruction


# --- media consent --------------------------------------------------------

def test_gallery_only_after_consent():
    state = State(stage=stages.PROPERTY_SELECTED, slots=QUALIFIED,
                  selected_property_id="PROP-001")
    plan = stages.decide(state, ex("wants_more_photos"), CATALOG, CATALOG)
    assert plan.send_gallery is WITH_MEDIA


def test_video_absent_offers_site_visit_instead():
    state = State(stage=stages.MEDIA_OFFERED, slots=QUALIFIED,
                  selected_property_id="PROP-001")
    plan = stages.decide(state, ex("wants_video"), CATALOG, CATALOG)
    assert plan.send_video is None
    assert "site visit" in plan.instruction


# --- booking --------------------------------------------------------------

def test_booking_request_asks_for_a_slot():
    state = State(stage=stages.MEDIA_OFFERED, slots=QUALIFIED, selected_property_id="PROP-001")
    plan = stages.decide(state, ex("wants_booking"), CATALOG, CATALOG)
    assert plan.stage == stages.BOOKING
    assert plan.booking_slot_text is None


def test_slot_given_confirms_with_maps_link():
    state = State(stage=stages.BOOKING, slots=QUALIFIED, selected_property_id="PROP-001")
    plan = stages.decide(state, ex("gave_slot", slot_text="Saturday 11am"), CATALOG, CATALOG)
    assert plan.stage == stages.CONFIRMED
    assert plan.booking_slot_text == "Saturday 11am"
    assert "https://maps/x" in plan.facts


def test_greeting_uses_the_lead_name():
    plan = stages.greet("Anita Rao", "PROP-001")
    assert "Anita Rao" in plan.facts
    assert plan.stage == stages.GREETED


# --- regressions found by the live end-to-end run -------------------------

def test_asking_for_photos_does_not_reselect_the_property():
    """The extractor fills reply_reference from history. Honouring it on every
    message pinned the stage at PROPERTY_SELECTED and the flow never advanced."""
    state = State(stage=stages.PROPERTY_SELECTED, slots=QUALIFIED,
                  selected_property_id="PROP-001")
    plan = stages.decide(state,
                         ex("wants_more_photos", reply_reference="Sobha Magnolia"),
                         CATALOG, CATALOG)
    assert plan.stage == stages.MEDIA_OFFERED, "must advance, not re-select"
    assert plan.send_gallery is WITH_MEDIA


def test_booking_request_advances_even_with_a_stale_reference():
    state = State(stage=stages.MEDIA_OFFERED, slots=QUALIFIED,
                  selected_property_id="PROP-001")
    plan = stages.decide(state, ex("wants_booking", reply_reference="Sobha Magnolia"),
                         CATALOG, CATALOG)
    assert plan.stage == stages.BOOKING


def test_slot_given_outside_booking_stage_still_books():
    """A lead who jumps straight to 'Saturday 11am' must still get recorded."""
    state = State(stage=stages.MEDIA_OFFERED, slots=QUALIFIED,
                  selected_property_id="PROP-001")
    plan = stages.decide(state, ex("gave_slot", slot_text="Saturday 11am"),
                         CATALOG, CATALOG)
    assert plan.stage == stages.CONFIRMED
    assert plan.booking_slot_text == "Saturday 11am"
