"""FastAPI entrypoint.

The webhook acks 200 immediately and processes in the background: Telegram
treats a slow handler as a failed delivery and redelivers, so acking first is
what keeps duplicates rare - and the processed_updates claim is what makes the
duplicates that still arrive harmless.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, Request, Response

from app import conversation
from app.config import load
from app.llm.client import make_client
from app.sheets.client import Sheets
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
        app.state.sheets = Sheets(app.state.settings)
        app.state.llm = make_client(app.state.settings)
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

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if chat_id is None or not text:
        return

    try:
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""
            if not token:
                await app.state.telegram.send_message(
                    chat_id, "Please use the link we sent you so I can find your enquiry.")
                return
            await conversation.start(app.state, chat_id, token)
        else:
            await conversation.message(app.state, chat_id, text, msg.get("message_id"))
    except Exception:
        log.exception("failed handling update %s", update_id)


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
