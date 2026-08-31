"""Matching is deterministic Python. The no-match path must stay honest."""
import pytest

from app.domain.matching import find, numbered_list
from app.domain.resolve import resolve
from app.sheets.properties import Property


def prop(pid, name, ptype, price, locality, status="active", media=""):
    return Property(
        property_id=pid, name=name, property_type=ptype, price_inr=price,
        locality=locality, city="Bengaluru", status=status,
        key_details="a\nb", maps_url="https://maps", media_folder=media,
        hero_file="Hero.png" if media else "",
        gallery_files=["Image 1.png"] if media else [],
    )


CATALOG = [
    prop("PROP-001", "Sobha Magnolia", "3BHK", 20_000_000, "Bengaluru-Mysuru Expressway", media="Sobha Magnolia"),
    prop("PROP-002", "Lakeview Enclave", "3BHK", 24_500_000, "Whitefield"),
    prop("PROP-003", "Green Meadows", "2BHK", 13_500_000, "Varthur"),
    prop("PROP-004", "Riverbend Residences", "3BHK", 18_500_000, "Bengaluru-Mysuru Expressway"),
    prop("PROP-005", "Sunridge Villas", "Villa", 42_000_000, "Kanakapura Road"),
    prop("PROP-006", "Hidden Heights", "3BHK", 19_000_000, "Whitefield", status="hidden"),
]


def test_hidden_properties_are_never_returned():
    active = [p for p in CATALOG if p.status == "active"]
    result = find(active, property_type="3BHK")
    assert all(p.property_id != "PROP-006" for p in result.matches)


def test_type_budget_and_area_together():
    result = find(CATALOG, property_type="3BHK", budget=20_000_000,
                  area="Bengaluru-Mysuru Expressway")
    assert result.exact
    assert {p.property_id for p in result.matches} == {"PROP-001", "PROP-004"}


def test_results_are_cheapest_first():
    result = find(CATALOG, property_type="3BHK")
    prices = [p.price_inr for p in result.matches]
    assert prices == sorted(prices)


def test_never_more_than_five():
    big = CATALOG * 3
    assert len(find(big).matches) <= 5


def test_budget_allows_modest_headroom():
    """A stated budget is a soft ceiling - 2cr should still surface a 2.05cr flat."""
    catalog = [prop("X", "Just Over", "3BHK", 20_500_000, "Whitefield")]
    assert find(catalog, budget=20_000_000).exact


def test_budget_excludes_what_is_far_over():
    catalog = [prop("X", "Way Over", "3BHK", 40_000_000, "Whitefield")]
    assert not find(catalog, budget=20_000_000).exact


def test_no_match_offers_alternatives_and_names_what_was_relaxed():
    """50L in Koramangala: nothing matches, so be honest and offer the nearest."""
    result = find(CATALOG, property_type="3BHK", budget=5_000_000, area="Koramangala")
    assert not result.exact
    assert result.alternatives, "must offer something rather than a dead end"
    assert result.relaxed is not None, "must know which constraint it dropped"


def test_area_matches_on_partial_wording():
    """A lead saying 'Mysuru Road' means the Bengaluru-Mysuru Expressway."""
    result = find(CATALOG, area="Mysuru Road")
    assert {p.property_id for p in result.matches} >= {"PROP-001", "PROP-004"}


def test_numbered_list_is_numbered_with_prices():
    text = numbered_list(find(CATALOG, property_type="3BHK").matches)
    assert text.startswith("1. ")
    assert "Rs" in text and "cr" in text


# --- resolving a reply to a shown listing ---------------------------------

SHOWN = CATALOG[:3]


@pytest.mark.parametrize("reply,expected", [("1", "PROP-001"), ("2", "PROP-002"), ("3.", "PROP-003")])
def test_resolve_by_number(reply, expected):
    p, needs_confirm = resolve(reply, SHOWN)
    assert p.property_id == expected and not needs_confirm


def test_resolve_by_exact_name():
    p, needs_confirm = resolve("Sobha Magnolia", SHOWN)
    assert p.property_id == "PROP-001" and not needs_confirm


def test_resolve_by_typo_asks_for_confirmation():
    p, needs_confirm = resolve("sobha magnolea", SHOWN)
    assert p.property_id == "PROP-001"
    assert needs_confirm, "a fuzzy match must be confirmed, never assumed"


def test_number_out_of_range_resolves_to_nothing():
    """Replying '7' to a list of 3 must not wrap around or guess."""
    p, _ = resolve("7", SHOWN)
    assert p is None


def test_unknown_property_resolves_to_nothing():
    p, _ = resolve("Prestige Shantiniketan", SHOWN)
    assert p is None, "never invent or substitute a property we don't have"
