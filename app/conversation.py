"""Executes one inbound message end to end.

Order of operations: claim the update, load state, extract intent, let the stage
machine decide, compose wording, send, persist. The model is consulted twice -
once to read the message, once to word the reply - and never to decide anything
in between.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.domain import stages
from app.llm import compose as composer
from app.llm import language as lang_rules
from app.llm.extract import extract
from app.media import sender
from app.sheets import bookings as sheet_bookings
from app.sheets import leads as sheet_leads
from app.sheets import properties as sheet_properties
from app.store import state as state_store

log = logging.getLogger("agent.conversation")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send_and_log(ctx, chat_id: int, lead_id: str, text: str) -> None:
    result = await ctx.telegram.send_message(chat_id, text)
    await state_store.log_message(ctx.store, lead_id, "out", text,
                                  result.get("message_id"))


async def start(ctx, chat_id: int, token: str) -> None:
    """Handle /start <token> from a per-lead deep link."""
    rows = await ctx.store.select("deep_link_tokens",
                                  {"token": f"eq.{token}", "select": "lead_id,used_at"})
    if not rows:
        log.warning("unknown deep-link token")
        await ctx.telegram.send_message(
            chat_id, "This link isn't valid. Please use the link we sent you.")
        return

    lead_id = rows[0]["lead_id"]
    lead = await sheet_leads.by_id(ctx.sheets, lead_id)
    if lead is None:
        log.error("token %s maps to lead %s which is not in the sheet", token, lead_id)
        return

    existing = await state_store.by_lead_id(ctx.store, lead_id)
    if existing and existing.opted_out:
        log.info("lead %s opted out, not re-engaging", lead_id)
        return

    st = existing or state_store.LeadState(lead_id=lead_id)
    st.chat_id = chat_id
    st.last_inbound_at = _now()

    if existing and existing.stage not in (stages.NEW, stages.GREETED):
        # A returning lead: restore, but re-confirm what we have on file.
        text = await composer.compose(
            ctx.llm, ctx.settings, language=st.language or "en",
            instruction=("They are back after a break. Welcome them back briefly and "
                         "re-confirm in one line whether the requirement below is still "
                         "right, before carrying on."),
            facts=_slot_facts(st, lead.name),
        )
    else:
        plan = stages.greet(lead.name, lead.enquired_about)
        st.stage = plan.stage
        text = await composer.compose(
            ctx.llm, ctx.settings, language=st.language or "en",
            instruction=plan.instruction, facts=plan.facts,
        )

    await state_store.upsert(ctx.store, st)
    await _send_and_log(ctx, chat_id, lead_id, text)
    await ctx.store.patch("deep_link_tokens", {"token": f"eq.{token}"}, {"used_at": _now()})


def _slot_facts(st, name: str) -> str:
    from app.domain.slots import format_inr
    bits = [f"Lead's name: {name}"]
    if st.property_type:
        bits.append(f"Property type on file: {st.property_type}")
    if st.budget:
        bits.append(f"Budget on file: {format_inr(st.budget)}")
    if st.area:
        bits.append(f"Area on file: {st.area}")
    return "\n".join(bits)


async def message(ctx, chat_id: int, text: str, telegram_message_id: int | None) -> None:
    """Handle an ordinary inbound message."""
    st = await state_store.by_chat_id(ctx.store, chat_id)
    if st is None:
        await ctx.telegram.send_message(
            chat_id, "Please start with the link we sent you so I can find your enquiry.")
        return
    if st.opted_out:
        log.info("lead %s opted out, ignoring inbound", st.lead_id)
        return

    await state_store.log_message(ctx.store, st.lead_id, "in", text, telegram_message_id)
    st.last_inbound_at = _now()
    st.nudged_at = None  # they replied, so the nudge budget resets

    properties = await sheet_properties.load_active(ctx.sheets)
    history_rows = await state_store.recent_messages(ctx.store, st.lead_id)
    history = state_store.transcript(history_rows)

    ex = await extract(ctx.llm, ctx.settings, text, context=history)

    chosen, pending = lang_rules.decide(
        st.language, ex.language, st.slots.get("pending_language"))
    st.language = chosen
    if pending:
        st.slots["pending_language"] = pending
    else:
        st.slots.pop("pending_language", None)

    # Rebuild in the order they were SHOWN, not sheet order - "1" means the first
    # line of the list the lead actually saw.
    by_id = {p.property_id: p for p in properties}
    shown = [by_id[pid] for pid in st.shown_property_ids if pid in by_id]
    plan = stages.decide(st, ex, properties, shown)

    if plan.silent:
        await state_store.upsert(ctx.store, st)
        return

    # Apply the plan's state changes before sending, so a crash mid-send cannot
    # leave us re-sending media the lead already has.
    st.stage = plan.stage
    for key, value in (("property_type", ex.property_type), ("budget", ex.budget),
                       ("area", ex.area)):
        if value:
            st.slots[key] = value
    if plan.shown:
        st.shown_property_ids = plan.shown
    if plan.selected:
        st.selected_property_id = plan.selected
    if plan.opted_out:
        st.opted_out = True
    await state_store.upsert(ctx.store, st)

    booking_facts = ""
    if plan.booking_slot_text and st.selected_property_id:
        booking_facts = await _record_booking(ctx, st, properties, plan.booking_slot_text)

    reply = await composer.compose(
        ctx.llm, ctx.settings, language=st.language,
        instruction=plan.instruction,
        facts=(plan.facts + ("\n" + booking_facts if booking_facts else "")),
        history=history,
    )

    # Hero goes with the reply; the album and video follow only on consent.
    if plan.send_hero is not None:
        await sender.send_hero(ctx.telegram, ctx.store, ctx.settings.supabase_url,
                               chat_id, st.lead_id, plan.send_hero)
    await _send_and_log(ctx, chat_id, st.lead_id, reply)

    if plan.send_gallery is not None:
        await sender.send_gallery(ctx.telegram, ctx.store, ctx.settings.supabase_url,
                                  chat_id, st.lead_id, plan.send_gallery)
    if plan.send_video is not None:
        await sender.send_video(ctx.telegram, ctx.store, ctx.settings.supabase_url,
                                chat_id, st.lead_id, plan.send_video)


async def _record_booking(ctx, st, properties, slot_text: str) -> str:
    """Record the booking before confirming it. Overlapping slots are allowed by
    decision; the sales team reconciles."""
    prop = next((p for p in properties if p.property_id == st.selected_property_id), None)
    if prop is None:
        return ""

    booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
    await ctx.store.insert("bookings", {
        "lead_id": st.lead_id, "property_id": prop.property_id,
        "slot_start": _now(), "status": "confirmed",
    })
    lead = await sheet_leads.by_id(ctx.sheets, st.lead_id)
    await sheet_bookings.append(
        ctx.sheets, booking_id=booking_id, lead_id=st.lead_id,
        lead_name=lead.name if lead else "", property_id=prop.property_id,
        property_name=prop.name, slot_date=slot_text, slot_time="",
        maps_url=prop.maps_url, created_at=_now(),
    )
    log.info("booking %s recorded for %s on %s", booking_id, st.lead_id, prop.property_id)
    return f"Booking is recorded (reference {booking_id})."
