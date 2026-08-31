"""Telegram file_id cache.

file_id is bot-specific and can go stale with no expiry guarantee, so a failed
send must trigger a re-send from the public URL and refresh the cache - never a
retry of the same id. file_path is never stored: it expires in about an hour.
"""
from app.store.client import Store

TABLE = "media_cache"


async def get(store: Store, property_id: str, file_key: str) -> str | None:
    rows = await store.select(TABLE, {
        "property_id": f"eq.{property_id}", "file_key": f"eq.{file_key}",
        "select": "telegram_file_id",
    })
    return rows[0]["telegram_file_id"] if rows else None


async def put(store: Store, property_id: str, file_key: str, kind: str, file_id: str) -> None:
    await store.insert(TABLE, {
        "property_id": property_id, "file_key": file_key,
        "kind": kind, "telegram_file_id": file_id,
    }, prefer="resolution=merge-duplicates")


async def already_sent(store: Store, lead_id: str, property_id: str, file_key: str) -> bool:
    rows = await store.select("media_sent", {
        "lead_id": f"eq.{lead_id}", "property_id": f"eq.{property_id}",
        "file_key": f"eq.{file_key}", "select": "id",
    })
    return bool(rows)


async def mark_sent(store: Store, lead_id: str, property_id: str, file_key: str) -> None:
    await store.insert("media_sent", {
        "lead_id": lead_id, "property_id": property_id, "file_key": file_key,
    }, prefer="resolution=merge-duplicates")
