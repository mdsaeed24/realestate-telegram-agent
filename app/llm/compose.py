"""Reply wording.

The caller has already decided what to say; this only chooses how to say it, in
the lead's language. Facts are passed in and must be reproduced exactly - the
model is told, and the prompt is built so it never has to guess a number.
"""
from app.config import Settings
from app.llm.client import text_of

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "kn": "Kannada", "ta": "Tamil", "kok": "Konkani",
}

SYSTEM = """You write a single WhatsApp-style message for a real estate salesperson \
in Bengaluru talking to a lead on Telegram.

Hard rules:
- Use ONLY the facts given to you. Never state a price, size, location, \
availability or detail that is not in the facts. If you do not have something, \
say you will find out.
- Never invent a property.
- Do not push. If the lead's budget or area does not fit, offer what does exist \
and move on. Never repeat a pitch they have already declined.
- Never say a booking is confirmed unless the facts say it is recorded.

Style:
- Sound like a real person texting, not a brochure or a bot. Short sentences.
- No greetings like "Dear customer". No emoji unless the lead uses them first.
- Write naturally in the target language as it is actually spoken in Bengaluru, \
including the English words people genuinely mix in. Do not produce stiff \
textbook translations.
- One message only. Do not sign off with a name."""


async def compose(
    client, settings: Settings, *, language: str, instruction: str, facts: str, history: str = ""
) -> str:
    lang = LANGUAGE_NAMES.get(language, "English")
    parts = [f"Write in: {lang}", "", f"What this message must do:\n{instruction}", ""]
    if facts:
        parts += [f"Facts you may use (and nothing beyond these):\n{facts}", ""]
    if history:
        parts += [f"Recent conversation:\n{history}", ""]
    parts.append("Write only the message text.")

    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": "\n".join(parts)}],
    )
    return text_of(response)
