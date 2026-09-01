"""Intent and slot extraction.

This returns structured data only. It never decides what happens next - Python
reads the result and decides. Budget wording is re-parsed deterministically by
domain.slots so that "2 cr" always means the same number.
"""
import json
from dataclasses import dataclass

from app.config import Settings
from app.domain.slots import looks_like_name, parse_budget, parse_phone, parse_type
from app.llm.client import text_of

INTENTS = (
    "still_looking", "not_looking", "gave_requirements", "picked_property",
    "wants_more_photos", "wants_video", "wants_booking", "gave_slot",
    "asked_question", "not_the_lead", "gave_contact", "other",
)

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "property_type": {"type": ["string", "null"]},
        "budget_text": {"type": ["string", "null"],
                        "description": "the budget exactly as the lead worded it"},
        "area": {"type": ["string", "null"]},
        "language": {"type": "string",
                     "enum": ["en", "hi", "kn", "ta", "kok"]},
        "reply_reference": {"type": ["string", "null"],
                            "description": "listing number or name if they picked one"},
        "slot_text": {"type": ["string", "null"]},
        "question": {"type": ["string", "null"]},
        "person_name": {"type": ["string", "null"],
                        "description": "their own name, if they state it"},
        "phone": {"type": ["string", "null"],
                  "description": "a phone number exactly as they wrote it"},
    },
    "required": ["intent", "language"],
    "additionalProperties": False,
}

SYSTEM = """You extract structured data from a property lead's Telegram message.

You do not decide anything and you do not write replies. Return only the fields \
in the schema.

Language: report the language the lead is actually writing in. Code-mixing is \
normal in India - "2 BHK chahiye Whitefield mein" is Hindi, and a single English \
loanword does not make a message English. Judge by the sentence structure and the \
majority of words.

budget_text: copy the lead's own wording ("around 2 cr", "80 lakhs"). Do not \
convert it to a number.

not_the_lead: use this when they say they are not the person we addressed, or \
that they are someone else, or that we have the wrong number.

gave_contact: use this when they give their own name or phone number.

person_name: only a name they state about themselves. Never copy the name we \
greeted them with.

Never invent a property name. reply_reference is only what the lead actually said."""


@dataclass(frozen=True)
class Extraction:
    intent: str
    language: str
    property_type: str | None = None
    budget: int | None = None
    area: str | None = None
    reply_reference: str | None = None
    slot_text: str | None = None
    question: str | None = None
    person_name: str | None = None
    phone: str | None = None


async def extract(client, settings: Settings, message: str, context: str = "") -> Extraction:
    prompt = f"{context}\n\nLead's message: {message}" if context else f"Lead's message: {message}"
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    data = json.loads(text_of(response))

    # Budget and phone are re-parsed in Python; the model only reports wording.
    budget_text = data.get("budget_text")
    raw_phone = data.get("phone")
    name = (data.get("person_name") or "").strip() or None
    return Extraction(
        intent=data.get("intent", "other"),
        language=data.get("language", "en"),
        property_type=parse_type(data.get("property_type") or "") or data.get("property_type"),
        budget=parse_budget(budget_text or ""),
        area=data.get("area"),
        reply_reference=data.get("reply_reference"),
        slot_text=data.get("slot_text"),
        question=data.get("question"),
        person_name=name if (name and looks_like_name(name)) else None,
        phone=parse_phone(raw_phone or "") or parse_phone(message),
    )
