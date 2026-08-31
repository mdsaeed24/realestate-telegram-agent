"""Resolving a lead's reply to one of the listings they were actually shown.

A reply that matches nothing is answered honestly - we never invent a property
or silently substitute a different one.
"""
import difflib
import re

from app.sheets.properties import Property


def resolve(reply: str, shown: list[Property]) -> tuple[Property | None, bool]:
    """Return (property, needs_confirmation).

    needs_confirmation is True for a fuzzy name match, which the caller should
    confirm in one line before acting on.
    """
    if not reply or not shown:
        return None, False

    text = reply.strip().lower()

    # A bare number referring to a position in the list.
    m = re.fullmatch(r"(?:no\.?\s*)?(\d+)\.?", text)
    if m:
        idx = int(m.group(1))
        if 1 <= idx <= len(shown):
            return shown[idx - 1], False
        return None, False  # out of range: say we don't have it

    # Exact or substring name match.
    for p in shown:
        if p.name.lower() == text or p.name.lower() in text:
            return p, False

    # Fuzzy match on the name, confirmed before use.
    names = [p.name.lower() for p in shown]
    close = difflib.get_close_matches(text, names, n=1, cutoff=0.6)
    if close:
        return shown[names.index(close[0])], True

    # A distinctive word from one name only.
    for p in shown:
        for word in p.name.lower().split():
            if len(word) > 4 and word in text:
                return p, True

    return None, False
