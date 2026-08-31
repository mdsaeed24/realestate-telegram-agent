"""The conversation stage machine.

This is the only place stage transitions happen, and it is pure: it takes state
plus an extraction and returns a Plan describing what should happen. It performs
no I/O and never calls the model. app/conversation.py executes the plan.
"""
from dataclasses import dataclass, field

from app.domain import matching, resolve
from app.domain.slots import format_inr
from app.sheets.properties import Property

NEW = "NEW"
GREETED = "GREETED"
QUALIFYING = "QUALIFYING"
LISTED = "LISTED"
PROPERTY_SELECTED = "PROPERTY_SELECTED"
MEDIA_OFFERED = "MEDIA_OFFERED"
BOOKING = "BOOKING"
CONFIRMED = "CONFIRMED"
NOT_LOOKING = "NOT_LOOKING"
PARKED = "PARKED"

TERMINAL = (NOT_LOOKING,)


@dataclass
class Plan:
    stage: str
    instruction: str = ""
    facts: str = ""
    silent: bool = False
    opted_out: bool = False
    shown: list[str] = field(default_factory=list)
    selected: str | None = None
    send_hero: Property | None = None
    send_gallery: Property | None = None
    send_video: Property | None = None
    booking_slot_text: str | None = None
    clear_selection: bool = False


def _property_facts(p: Property) -> str:
    lines = [
        f"Name: {p.name}",
        f"Type: {p.property_type}",
        f"Price: {format_inr(p.price_inr)}",
        f"Location: {p.locality}, {p.city}",
    ]
    if p.bullets:
        lines.append("Details:")
        lines += [f"- {b}" for b in p.bullets]
    return "\n".join(lines)


def _missing_slots(state) -> list[str]:
    missing = []
    if not state.property_type:
        missing.append("what kind of property")
    if not state.budget:
        missing.append("what budget")
    if not state.area:
        missing.append("which area")
    return missing


def greet(lead_name: str, enquired_about: str | None) -> Plan:
    """Opening message: greet by name, remind them what they enquired about."""
    facts = f"Lead's name: {lead_name}"
    if enquired_about:
        facts += f"\nThey previously enquired about: {enquired_about}"
    return Plan(
        stage=GREETED,
        instruction=(
            "Greet them by name, remind them they enquired about a property with us, "
            "and ask if they are still looking. Keep it to two short sentences."
        ),
        facts=facts,
    )


def decide(state, ex, properties: list[Property], shown: list[Property]) -> Plan:
    """Given current state and what the lead just said, decide what happens next."""

    if state.opted_out or state.stage in TERMINAL:
        return Plan(stage=state.stage, silent=True)

    if ex.intent == "not_looking":
        return Plan(
            stage=NOT_LOOKING,
            opted_out=True,
            instruction=(
                "They said they are not looking any more. Thank them warmly, wish them "
                "well, and make clear we will not keep messaging. Do not ask anything."
            ),
        )

    # Absorb any requirements mentioned, whatever the stage.
    slots_now = dict(state.slots)
    for key, value in (("property_type", ex.property_type), ("budget", ex.budget), ("area", ex.area)):
        if value:
            slots_now[key] = value

    class _Merged:
        slots = slots_now
        property_type = slots_now.get("property_type")
        budget = slots_now.get("budget")
        area = slots_now.get("area")
        qualified = bool(slots_now.get("property_type") and slots_now.get("budget")
                         and slots_now.get("area"))

    merged = _Merged()

    # Picking a listing they were shown. Only when they are actually picking:
    # the extractor also fills reply_reference from conversation history, and
    # honouring that on every message re-selects the property forever.
    picking = ex.intent == "picked_property" or (
        state.stage == LISTED and ex.intent in ("other", "gave_requirements")
    )
    if picking and state.stage in (LISTED, PROPERTY_SELECTED, MEDIA_OFFERED) and ex.reply_reference:
        picked, needs_confirm = resolve.resolve(ex.reply_reference, shown)
        if picked is None:
            return Plan(
                stage=state.stage,
                instruction=(
                    "They referred to a property we do not have on the list we showed. "
                    "Say plainly that we do not have that one, then show the same "
                    "numbered list again. Do not invent anything."
                ),
                facts=matching.numbered_list(shown),
            )
        if needs_confirm:
            return Plan(
                stage=state.stage,
                instruction=(
                    f"Ask in one short line whether they meant {picked.name}. "
                    "Do not send details until they confirm."
                ),
                facts=f"Candidate: {picked.name}",
            )
        return _selected_plan(picked)

    if ex.intent == "wants_more_photos" and state.selected_property_id:
        prop = _by_id(properties, state.selected_property_id)
        if prop and prop.has_gallery:
            return Plan(
                stage=MEDIA_OFFERED, send_gallery=prop,
                instruction=("Say here are the rest of the photos, in one short line. "
                             "Then ask if they would like to see a video."),
                facts=f"Property: {prop.name}",
            )
        return Plan(
            stage=MEDIA_OFFERED,
            instruction=("Say we do not have more photos for this one yet, and offer to "
                         "arrange a site visit instead."),
            facts=f"Property: {prop.name if prop else 'the selected property'}",
        )

    if ex.intent == "wants_video" and state.selected_property_id:
        prop = _by_id(properties, state.selected_property_id)
        if prop and prop.has_video:
            return Plan(stage=MEDIA_OFFERED, send_video=prop,
                        instruction="Say here is the video, in one short line.",
                        facts=f"Property: {prop.name}")
        return Plan(
            stage=MEDIA_OFFERED,
            instruction=("Say we do not have a video for this one yet. Offer a site visit "
                         "so they can see it in person."),
            facts=f"Property: {prop.name if prop else ''}",
        )

    if ex.intent in ("wants_booking", "gave_slot") or state.stage == BOOKING:
        if ex.slot_text:
            prop = _by_id(properties, state.selected_property_id or "")
            return Plan(
                stage=CONFIRMED,
                booking_slot_text=ex.slot_text,
                instruction=(
                    "Confirm the site visit is booked for the date and time given, and "
                    "share the maps link so they can find it. Two short sentences."
                ),
                facts=(f"Property: {prop.name if prop else ''}\n"
                       f"Slot: {ex.slot_text}\n"
                       f"Maps link: {prop.maps_url if prop else ''}"),
            )
        return Plan(
            stage=BOOKING,
            instruction=("They want to book a site visit. Ask which date and what time "
                         "suits them. One short question."),
            facts="",
        )

    # Past qualification, ordinary conversation must not re-trigger a listing.
    # Falling through to the matcher on every message re-pitched the same
    # properties after a booking was already confirmed.
    if state.stage in (LISTED, PROPERTY_SELECTED, MEDIA_OFFERED, CONFIRMED) and \
            ex.intent in ("asked_question", "other", "still_looking"):
        return _followup(state, ex, properties)

    # Qualification.
    if not merged.qualified:
        missing = _missing_slots(merged)
        if state.stage in (NEW, GREETED) and ex.intent in ("still_looking", "other", "asked_question"):
            return Plan(
                stage=QUALIFYING,
                instruction=("They are still looking. Ask what kind of property, what "
                             "budget, and which area - in one natural message, not a list."),
                facts="",
            )
        return Plan(
            stage=QUALIFYING,
            instruction=(f"Ask only for what is still missing: {', '.join(missing)}. "
                         "One short, natural question."),
            facts="",
        )

    # Fully qualified: show what matches.
    result = matching.find(
        properties, property_type=merged.property_type,
        budget=merged.budget, area=merged.area,
    )
    if result.exact:
        return Plan(
            stage=LISTED,
            shown=[p.property_id for p in result.matches],
            instruction=(
                "Show these as a numbered list with prices, exactly as given. Add one "
                "short line before it, and afterwards invite them to reply with a number "
                "to see more."
            ),
            facts=matching.numbered_list(result.matches),
        )

    dropped = {
        "area": "nothing in that area at that budget",
        "budget": "nothing at that budget in that area",
        "type": "nothing of that type there",
        "everything": "nothing matching that",
    }.get(result.relaxed or "", "nothing matching that")

    return Plan(
        stage=LISTED,
        shown=[p.property_id for p in result.alternatives],
        instruction=(
            f"Say honestly that we have {dropped} right now. Then offer these closest "
            "options as a numbered list with prices, and ask if any of them work. "
            "Do not push and do not repeat the pitch."
        ),
        facts=matching.numbered_list(result.alternatives),
    )


def _followup(state, ex, properties: list[Property]) -> Plan:
    """Answer what was said without re-pitching. The brief is explicit: never
    repeat a pitch, and never behave like a broadcast."""
    prop = _by_id(properties, state.selected_property_id or "")

    if state.stage == CONFIRMED:
        facts = "Their site visit is already booked and recorded."
        if prop:
            facts += f"\nProperty: {prop.name}\nMaps link: {prop.maps_url}"
        if ex.question:
            return Plan(
                stage=CONFIRMED,
                instruction=("Answer their question using only the facts below. If the "
                             "answer is not there, say you will check and come back. Do "
                             "NOT list properties again and do not repeat the pitch."),
                facts=facts + (f"\n{_property_facts(prop)}" if prop else ""),
            )
        return Plan(
            stage=CONFIRMED,
            instruction=("Reply briefly and warmly to what they said - one or two lines. "
                         "Their visit is booked, so there is nothing to sell. Do NOT list "
                         "properties and do NOT repeat any details unless asked."),
            facts=facts,
        )

    if ex.question:
        return Plan(
            stage=state.stage,
            instruction=("Answer their question using only the facts below. If it is not "
                         "there, say you will find out. Do not re-list properties."),
            facts=_property_facts(prop) if prop else "",
        )

    return Plan(
        stage=state.stage,
        instruction=("Reply briefly to what they said - one or two lines. Do not re-list "
                     "properties and do not repeat the pitch."),
        facts=_property_facts(prop) if prop else "",
    )


def _selected_plan(prop: Property) -> Plan:
    if prop.has_media:
        return Plan(
            stage=PROPERTY_SELECTED,
            selected=prop.property_id,
            send_hero=prop,
            instruction=(
                "Give the key details as short bullet points, exactly as provided. Then "
                "ask if they would like to see more photos or a video. The main photo is "
                "being sent with this message."
            ),
            facts=_property_facts(prop),
        )
    return Plan(
        stage=PROPERTY_SELECTED,
        selected=prop.property_id,
        instruction=(
            "Give the key details as short bullet points, exactly as provided. Then say "
            "photos for this one are not up yet, and offer a site visit instead. This is "
            "normal, so do not apologise heavily."
        ),
        facts=_property_facts(prop),
    )


def _by_id(properties: list[Property], property_id: str) -> Property | None:
    return next((p for p in properties if p.property_id == property_id), None)
