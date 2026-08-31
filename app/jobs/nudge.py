"""One follow-up for a lead who went quiet, then never again.

The brief is emphatic about not spamming, so this is deliberately narrow: one
nudge, only for a lead mid-conversation, never for an opted-out or finished one,
and nudged_at is stamped so it cannot fire twice.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import load
from app.domain import stages
from app.llm import compose as composer
from app.llm.client import make_client
from app.sheets.client import Sheets
from app.store import state as state_store
from app.store.client import Store
from app.telegram.client import Telegram

log = logging.getLogger("agent.nudge")

QUIET_HOURS = 24

# Stages worth nudging: the lead engaged but stopped before deciding anything.
NUDGEABLE = (stages.GREETED, stages.QUALIFYING, stages.LISTED,
             stages.PROPERTY_SELECTED, stages.MEDIA_OFFERED)


def is_due(row: dict, now: datetime, quiet_hours: int = QUIET_HOURS) -> bool:
    """Pure predicate so the rule can be tested without a database."""
    if row.get("opted_out"):
        return False
    if row.get("nudged_at"):
        return False
    if row.get("stage") not in NUDGEABLE:
        return False
    last = row.get("last_inbound_at")
    if not last:
        return False
    if isinstance(last, str):
        last = datetime.fromisoformat(last.replace("Z", "+00:00"))
    return (now - last) >= timedelta(hours=quiet_hours)


async def run_once(ctx) -> int:
    rows = await ctx.store.select("leads_state", {
        "select": "*", "opted_out": "eq.false", "nudged_at": "is.null",
    })
    now = datetime.now(timezone.utc)
    due = [r for r in rows if is_due(r, now)]
    log.info("%s leads quiet, %s due a nudge", len(rows), len(due))

    sent = 0
    for row in due:
        st = state_store._from_row(row)
        if not st.chat_id:
            continue
        history = state_store.transcript(
            await state_store.recent_messages(ctx.store, st.lead_id, limit=4))
        text = await composer.compose(
            ctx.llm, ctx.settings, language=st.language or "en",
            instruction=("They went quiet a day ago. Send ONE short, low-pressure "
                         "follow-up that picks up where the conversation stopped. Do not "
                         "repeat the pitch and do not ask more than one question."),
            facts="", history=history,
        )
        await ctx.telegram.send_message(st.chat_id, text)
        await state_store.log_message(ctx.store, st.lead_id, "out", text)
        st.nudged_at = now.isoformat()
        await state_store.upsert(ctx.store, st)
        sent += 1
    return sent


class _Ctx:
    def __init__(self):
        self.settings = load()
        self.store = Store(self.settings)
        self.telegram = Telegram(self.settings)
        self.sheets = Sheets(self.settings)
        self.llm = make_client(self.settings)

    async def aclose(self):
        await self.store.aclose()
        await self.telegram.aclose()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ctx = _Ctx()
    try:
        sent = await run_once(ctx)
        print(f"nudges sent: {sent}")
    finally:
        await ctx.aclose()


if __name__ == "__main__":
    asyncio.run(main())
