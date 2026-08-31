"""One nudge, then never again - the no-spam rule, tested."""
from datetime import datetime, timedelta, timezone

from app.domain import stages
from app.jobs.nudge import is_due

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def row(**kw):
    base = {
        "opted_out": False, "nudged_at": None, "stage": stages.QUALIFYING,
        "last_inbound_at": (NOW - timedelta(hours=30)).isoformat(),
    }
    return {**base, **kw}


def test_quiet_for_a_day_is_due():
    assert is_due(row(), NOW)


def test_recently_active_is_not_due():
    assert not is_due(row(last_inbound_at=(NOW - timedelta(hours=2)).isoformat()), NOW)


def test_already_nudged_is_never_nudged_again():
    """The whole point: exactly one follow-up, ever."""
    assert not is_due(row(nudged_at=(NOW - timedelta(hours=5)).isoformat()), NOW)


def test_opted_out_is_never_nudged():
    assert not is_due(row(opted_out=True), NOW)


def test_finished_conversation_is_not_nudged():
    assert not is_due(row(stage=stages.CONFIRMED), NOW)


def test_not_looking_is_not_nudged():
    assert not is_due(row(stage=stages.NOT_LOOKING), NOW)


def test_lead_who_never_spoke_is_not_nudged():
    assert not is_due(row(last_inbound_at=None), NOW)
