"""Normalising what a lead said into numbers Python can filter on.

Budget parsing is deterministic: an LLM must never decide what "2 cr" means,
because the same phrase has to mean the same number every time.
"""
import re

CRORE = 10_000_000
LAKH = 100_000

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "half": 0.5, "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
}

_CRORE_WORDS = r"(?:cr|crore|crores|karod|kodi)"
_LAKH_WORDS = r"(?:l|lac|lakh|lakhs|lakshya)"


def parse_budget(text: str) -> int | None:
    """Return a rupee amount, or None when nothing budget-shaped is present."""
    if not text:
        return None
    t = text.lower().replace(",", "")

    for word, value in _WORD_NUMBERS.items():
        t = re.sub(rf"\b{word}\b", str(value), t)

    m = re.search(rf"(\d+(?:\.\d+)?)\s*{_CRORE_WORDS}\b", t)
    if m:
        return int(float(m.group(1)) * CRORE)

    m = re.search(rf"(\d+(?:\.\d+)?)\s*{_LAKH_WORDS}\b", t)
    if m:
        return int(float(m.group(1)) * LAKH)

    # A bare number large enough to be a price in rupees.
    m = re.search(r"\b(\d{6,})\b", t)
    if m:
        return int(m.group(1))
    return None


def budget_window(amount: int | None, tolerance: float = 0.15) -> tuple[int, int]:
    """A stated budget is a soft ceiling; allow a little headroom above it."""
    if not amount:
        return (0, 0)
    return (int(amount * (1 - tolerance)), int(amount * (1 + tolerance)))


_TYPE_PATTERNS = [
    (re.compile(r"\b(\d)\s*bhk\b"), lambda m: f"{m.group(1)}BHK"),
    (re.compile(r"\bvilla\b"), lambda m: "Villa"),
    (re.compile(r"\bplot\b"), lambda m: "Plot"),
    (re.compile(r"\bapartment\b|\bflat\b"), lambda m: None),
]


def parse_type(text: str) -> str | None:
    if not text:
        return None
    t = text.lower()
    for pattern, render in _TYPE_PATTERNS:
        m = pattern.search(t)
        if m:
            return render(m)
    return None


def format_inr(amount: int) -> str:
    """Indian price formatting: crores and lakhs, not millions."""
    if amount >= CRORE:
        value = amount / CRORE
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return f"Rs {text} cr"
    if amount >= LAKH:
        value = amount / LAKH
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return f"Rs {text} lakh"
    return f"Rs {amount:,}"
