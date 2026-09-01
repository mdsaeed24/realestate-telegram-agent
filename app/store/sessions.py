"""Session records - one per conversation.

The agent never assumes the person holding a deep link is the lead it names, so
every /start opens a session that records who actually turned up, whether they
matched the expected lead, and how the conversation ended.
"""
import uuid
from datetime import datetime, timezone

from app.store.client import Store

TABLE = "sessions"


def new_ref() -> str:
    return f"S-{uuid.uuid4().hex[:10].upper()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def open_session(store: Store, chat_id: int, expected_lead_id: str | None) -> str:
    ref = new_ref()
    await store.insert(TABLE, {
        "session_ref": ref,
        "chat_id": chat_id,
        "expected_lead_id": expected_lead_id,
        "identity_match": "unknown",
    })
    return ref


async def current(store: Store, chat_id: int) -> dict | None:
    rows = await store.select(TABLE, {
        "chat_id": f"eq.{chat_id}", "select": "*",
        "order": "started_at.desc", "limit": "1",
    })
    return rows[0] if rows else None


async def record_identity(store: Store, session_ref: str, *, lead_id: str,
                          name: str, phone: str | None, match: str) -> None:
    await store.patch(TABLE, {"session_ref": f"eq.{session_ref}"}, {
        "lead_id": lead_id, "claimed_name": name, "claimed_phone": phone,
        "identity_match": match, "last_activity_at": _now(),
    })


async def touch(store: Store, session_ref: str, outcome: str | None = None) -> None:
    row = {"last_activity_at": _now()}
    if outcome:
        row["outcome"] = outcome
    await store.patch(TABLE, {"session_ref": f"eq.{session_ref}"}, row)
