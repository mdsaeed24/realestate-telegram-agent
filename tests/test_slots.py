"""Budget parsing must be deterministic - the same phrase always means the same
number, in every language a lead might use."""
import pytest

from app.domain.slots import format_inr, parse_budget, parse_type


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2 cr", 20_000_000),
        ("2 crore", 20_000_000),
        ("around 2 crore", 20_000_000),
        ("2.5cr", 25_000_000),
        ("1.5 crores", 15_000_000),
        ("two crore", 20_000_000),
        ("do crore", 20_000_000),          # Hindi
        ("80 lakh", 8_000_000),
        ("80 lakhs", 8_000_000),
        ("80L", 8_000_000),
        ("50 lac", 5_000_000),
        ("20000000", 20_000_000),
        ("budget is around 1.2 cr max", 12_000_000),
    ],
)
def test_parse_budget(text, expected):
    assert parse_budget(text) == expected


@pytest.mark.parametrize("text", ["", "no idea", "3bhk", "next week", "yes"])
def test_parse_budget_returns_none_when_absent(text):
    assert parse_budget(text) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("3 bhk", "3BHK"),
        ("3BHK", "3BHK"),
        ("looking for a 2bhk", "2BHK"),
        ("villa please", "Villa"),
        ("a plot", "Plot"),
    ],
)
def test_parse_type(text, expected):
    assert parse_type(text) == expected


@pytest.mark.parametrize(
    "amount,expected",
    [
        (20_000_000, "Rs 2 cr"),
        (24_500_000, "Rs 2.45 cr"),
        (13_500_000, "Rs 1.35 cr"),
        (8_000_000, "Rs 80 lakh"),
        (50_000, "Rs 50,000"),
    ],
)
def test_format_inr_uses_indian_units(amount, expected):
    """A lead in Bengaluru reads crores and lakhs, not millions."""
    assert format_inr(amount) == expected
