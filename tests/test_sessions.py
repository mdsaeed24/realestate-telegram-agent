"""Identity is asked for every time, and matching decides whether a person
inherits an existing lead record or becomes a new client."""
import pytest

from app.conversation import names_match


@pytest.mark.parametrize("claimed,expected", [
    ("Anita Rao", "Anita Rao"),
    ("Anita", "Anita Rao"),          # first name only
    ("anita rao", "Anita Rao"),      # case
    ("Rao", "Anita Rao"),            # surname only
    ("A. Rao", "Anita Rao"),
])
def test_same_person_matches(claimed, expected):
    assert names_match(claimed, expected)


@pytest.mark.parametrize("claimed,expected", [
    ("Sayeed", "Anita Rao"),
    ("Vikram Shetty", "Anita Rao"),
    ("Priya Nair", "Anita Rao"),
    ("", "Anita Rao"),
    ("Anita Rao", ""),
])
def test_different_person_does_not_match(claimed, expected):
    """A different person must never inherit someone else's lead record."""
    assert not names_match(claimed, expected)


def test_single_letters_are_ignored():
    """'A' alone must not match 'Anita' - too weak to identify anyone."""
    assert not names_match("A", "Anita Rao")
