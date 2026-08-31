"""'1' must mean the first line of the list the lead actually saw.

Rebuilding the shown list by filtering sheet order silently renumbers it, so a
lead picking 1 gets a different property than the one they read.
"""
from app.domain.resolve import resolve
from app.sheets.properties import Property


def prop(pid, name, price):
    return Property(
        property_id=pid, name=name, property_type="3BHK", price_inr=price,
        locality="Bengaluru-Mysuru Expressway", city="Bengaluru", status="active",
        key_details="x", maps_url="", media_folder="", hero_file="",
    )


# Sheet order is PROP-001 first; the lead was shown cheapest-first, so PROP-004 was #1.
SHEET_ORDER = [prop("PROP-001", "Sobha Magnolia", 20_000_000),
               prop("PROP-004", "Riverbend Residences", 18_500_000)]
SHOWN_IDS = ["PROP-004", "PROP-001"]


def rebuild(properties, shown_ids):
    by_id = {p.property_id: p for p in properties}
    return [by_id[pid] for pid in shown_ids if pid in by_id]


def test_rebuild_preserves_displayed_order():
    shown = rebuild(SHEET_ORDER, SHOWN_IDS)
    assert [p.property_id for p in shown] == SHOWN_IDS


def test_reply_one_selects_what_was_listed_first():
    shown = rebuild(SHEET_ORDER, SHOWN_IDS)
    picked, _ = resolve("1", shown)
    assert picked.property_id == "PROP-004", "must be the property shown as line 1"


def test_naive_filter_would_pick_the_wrong_one():
    """Documents the bug this guards against."""
    naive = [p for p in SHEET_ORDER if p.property_id in SHOWN_IDS]
    picked, _ = resolve("1", naive)
    assert picked.property_id == "PROP-001", "the wrong property - hence the fix"
