"""Language is detected once and held for the conversation.

Code-mixing is normal, so a single foreign word must not flip the language.
A switch requires the extractor to report a different language on two
consecutive substantive messages.
"""
SUPPORTED = ("en", "hi", "kn", "ta", "kok")


def decide(stored: str | None, detected: str | None, pending: str | None) -> tuple[str, str | None]:
    """Return (language_to_use, new_pending_switch).

    stored  - the language held for this lead so far
    detected- what the extractor reported for this message
    pending - a candidate switch seen on the previous message
    """
    if detected not in SUPPORTED:
        return stored or "en", None
    if not stored:
        return detected, None
    if detected == stored:
        return stored, None
    if pending == detected:
        return detected, None      # two in a row: a real switch
    return stored, detected        # first sighting: hold, remember the candidate
