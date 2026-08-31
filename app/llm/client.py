"""Anthropic client. The model id lives only in config, so switching models is
a config change (BUILD_SPEC Phase 5)."""
import anthropic

from app.config import Settings


def make_client(settings: Settings) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def text_of(response) -> str:
    """Pull the visible text out of a response that may lead with thinking blocks."""
    return "".join(b.text for b in response.content if b.type == "text").strip()
