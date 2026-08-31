"""Deterministic property matching. The LLM never decides which properties match.

When nothing matches, we say so and offer the nearest real alternatives rather
than silently widening the search - showing properties the lead didn't ask for
without saying why is a form of pushing.
"""
import re
from dataclasses import dataclass

from app.domain.slots import budget_window
from app.sheets.properties import Property

MAX_RESULTS = 5


@dataclass(frozen=True)
class MatchResult:
    matches: list[Property]
    alternatives: list[Property]
    relaxed: str | None  # which constraint was dropped to find alternatives

    @property
    def exact(self) -> bool:
        return bool(self.matches)


def _area_matches(prop: Property, area: str) -> bool:
    if not area:
        return True
    a = area.lower().strip()
    locality = prop.locality.lower()
    city = prop.city.lower()

    if a in locality:
        return True
    if a == city:
        return True

    # Match on any significant word, so "Mysuru Road" finds the
    # "Bengaluru-Mysuru Expressway". The city name is excluded: a lead asking for
    # one Bengaluru locality must not match every Bengaluru property.
    words = [w for w in re.split(r"[\s\-,]+", a) if len(w) > 3 and w != city]
    return any(w in locality for w in words)


def _type_matches(prop: Property, wanted: str) -> bool:
    if not wanted:
        return True
    return prop.property_type.lower() == wanted.lower()


def _budget_matches(prop: Property, budget: int | None) -> bool:
    if not budget:
        return True
    low, high = budget_window(budget)
    return prop.price_inr <= high


def find(
    properties: list[Property],
    *,
    property_type: str | None = None,
    budget: int | None = None,
    area: str | None = None,
) -> MatchResult:
    # Only active rows are ever shown, enforced here rather than trusting callers.
    properties = [p for p in properties if p.status == "active"]

    matches = [
        p for p in properties
        if _type_matches(p, property_type or "")
        and _budget_matches(p, budget)
        and _area_matches(p, area or "")
    ]
    matches.sort(key=lambda p: p.price_inr)
    if matches:
        return MatchResult(matches[:MAX_RESULTS], [], None)

    # Nothing matched. Drop one constraint at a time, most-negotiable first, and
    # report which one we dropped so the reply can be honest about it.
    for relaxed, candidates in (
        ("area", [p for p in properties
                  if _type_matches(p, property_type or "") and _budget_matches(p, budget)]),
        ("budget", [p for p in properties
                    if _type_matches(p, property_type or "") and _area_matches(p, area or "")]),
        ("type", [p for p in properties
                  if _budget_matches(p, budget) and _area_matches(p, area or "")]),
    ):
        if candidates:
            candidates.sort(key=lambda p: abs(p.price_inr - (budget or p.price_inr)))
            return MatchResult([], candidates[:3], relaxed)

    cheapest = sorted(properties, key=lambda p: p.price_inr)[:3]
    return MatchResult([], cheapest, "everything")


def numbered_list(properties: list[Property]) -> str:
    from app.domain.slots import format_inr

    lines = []
    for i, p in enumerate(properties, 1):
        lines.append(f"{i}. {p.name} - {p.property_type}, {format_inr(p.price_inr)}, {p.locality}")
    return "\n".join(lines)
