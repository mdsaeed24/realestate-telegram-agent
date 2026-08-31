"""A code-mixed message must not flip the conversation's language."""
from app.llm.language import decide


def test_first_message_sets_the_language():
    assert decide(None, "hi", None) == ("hi", None)


def test_same_language_holds():
    assert decide("hi", "hi", None) == ("hi", None)


def test_single_odd_detection_does_not_switch():
    """One English-looking message inside a Hindi conversation holds Hindi."""
    lang, pending = decide("hi", "en", None)
    assert lang == "hi"
    assert pending == "en", "remember the candidate but do not act on it yet"


def test_two_consecutive_switch():
    lang, pending = decide("hi", "en", "en")
    assert lang == "en" and pending is None


def test_flip_flop_does_not_switch():
    """hi -> en -> kn: two different candidates in a row is noise, not a switch."""
    lang, pending = decide("hi", "en", None)
    lang2, pending2 = decide(lang, "kn", pending)
    assert lang2 == "hi", "still Hindi - no language was seen twice running"


def test_unsupported_detection_is_ignored():
    assert decide("hi", "fr", None) == ("hi", None)
