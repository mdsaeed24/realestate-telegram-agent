"""FastAPI entrypoint.

The webhook acks 200 immediately and processes in the background: Telegram
treats a slow handler as a failed delivery and redelivers, so acking first is
what keeps duplicates rare - and the processed_updates claim is what makes the
duplicates that still arrive harmless.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, Request, Response

from app.config import load
from app.store.client import Store
from app.store.updates import claim
from app.telegram.client import Telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("agent")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests pre-populate state with fakes; only build real clients if they didn't.
    if not getattr(app.state, "configured", False):
        app.state.settings = load()
        app.state.store = Store(app.state.settings)
        app.state.telegram = Telegram(app.state.settings)
        app.state.configured = True
    yield
    await app.state.store.aclose()
    if app.state.telegram is not None:
        await app.state.telegram.aclose()


app = FastAPI(title="realestate-telegram-agent", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


async def handle_update(update: dict) -> None:
    """Process one update. Runs after the ack has already gone out."""
    update_id = update.get("update_id")
    if update_id is None:
        log.warning("update with no update_id, ignoring")
        return

    if not await claim(app.state.store, update_id):
        log.info("update %s already processed, skipping", update_id)
        return

    log.info("processing update %s", update_id)
    # Phase 4 onward: resolve the lead, run the stage machine, reply.


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    secret = app.state.settings.telegram_webhook_secret
    if x_telegram_bot_api_secret_token != secret:
        log.warning("webhook called with a bad secret token")
        return Response(status_code=403)

    update = await request.json()
    background.add_task(handle_update, update)
    return Response(status_code=200)
