"""The idempotency gate.

Telegram redelivers an update when our ack is slow or fails. Claiming the
update_id in Postgres - not in process memory - is what makes double-processing
impossible across restarts and concurrent workers.
"""
from app.store.client import Store

UNIQUE_VIOLATION = "23505"


async def claim(store: Store, update_id: int) -> bool:
    """Return True if this update is ours to process, False if already seen."""
    r = await store.insert("processed_updates", {"update_id": update_id})
    if r.status_code in (200, 201, 204):
        return True
    if r.status_code == 409 or UNIQUE_VIOLATION in r.text:
        return False
    r.raise_for_status()
    return False
