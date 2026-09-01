"""Conversation state. Everything that must survive a restart lives here."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.store.client import Store

TABLE = "leads_state"


@dataclass
class LeadState:
    lead_id: str
    chat_id: int | None = None
    stage: str = "NEW"
    language: str | None = None
    slots: dict = field(default_factory=dict)
    shown_property_ids: list[str] = field(default_factory=list)
    selected_property_id: str | None = None
    opted_out: bool = False
    last_inbound_at: str | None = None
    nudged_at: str | None = None

    @property
    def budget(self) -> int | None:
        return self.slots.get("budget")

    @property
    def property_type(self) -> str | None:
        return self.slots.get("property_type")

    @property
    def area(self) -> str | None:
        return self.slots.get("area")

    @property
    def qualified(self) -> bool:
        return bool(self.property_type and self.budget and self.area)


def _from_row(row: dict) -> LeadState:
    slots = row.get("slots") or {}
    if isinstance(slots, str):
        slots = json.loads(slots)
    return LeadState(
        lead_id=row["lead_id"],
        chat_id=row.get("chat_id"),
        stage=row.get("stage", "NEW"),
        language=row.get("language"),
        slots=slots,
        shown_property_ids=row.get("shown_property_ids") or [],
        selected_property_id=row.get("selected_property_id"),
        opted_out=bool(row.get("opted_out")),
        last_inbound_at=row.get("last_inbound_at"),
        nudged_at=row.get("nudged_at"),
    )


async def by_chat_id(store: Store, chat_id: int) -> LeadState | None:
    rows = await store.select(TABLE, {"chat_id": f"eq.{chat_id}", "select": "*"})
    return _from_row(rows[0]) if rows else None


async def by_lead_id(store: Store, lead_id: str) -> LeadState | None:
    rows = await store.select(TABLE, {"lead_id": f"eq.{lead_id}", "select": "*"})
    return _from_row(rows[0]) if rows else None


async def upsert(store: Store, state: LeadState) -> None:
    row = {
        "lead_id": state.lead_id,
        "chat_id": state.chat_id,
        "stage": state.stage,
        "language": state.language,
        "slots": state.slots,
        "shown_property_ids": state.shown_property_ids,
        "selected_property_id": state.selected_property_id,
        "opted_out": state.opted_out,
        "last_inbound_at": state.last_inbound_at,
        "nudged_at": state.nudged_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await store.insert(TABLE, row, prefer="resolution=merge-duplicates")
    if r.status_code >= 400:
        r.raise_for_status()


async def log_message(store: Store, lead_id: str, direction: str, body: str,
                      telegram_message_id: int | None = None,
                      session_ref: str | None = None) -> None:
    await store.insert("messages", {
        "lead_id": lead_id, "direction": direction, "body": body,
        "telegram_message_id": telegram_message_id, "session_ref": session_ref,
    })


async def recent_messages(store: Store, lead_id: str, limit: int = 8) -> list[dict]:
    rows = await store.select("messages", {
        "lead_id": f"eq.{lead_id}", "select": "direction,body,created_at",
        "order": "created_at.desc", "limit": str(limit),
    })
    return list(reversed(rows))


def transcript(rows: list[dict]) -> str:
    return "\n".join(
        f"{'Lead' if r['direction'] == 'in' else 'Agent'}: {r['body']}" for r in rows
    )
