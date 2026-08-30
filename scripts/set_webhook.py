"""Register the webhook with Telegram. Pass the public base URL as argv[1].

setWebhook is an explicit call - nothing else triggers it. Re-run it every time
the tunnel URL changes.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.config import load  # noqa: E402
from app.telegram.client import Telegram, TelegramError  # noqa: E402


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/set_webhook.py https://<tunnel-host>")
        return 2

    base = sys.argv[1].rstrip("/")
    url = f"{base}/webhook/telegram"
    s = load()
    tg = Telegram(s)
    try:
        await tg.set_webhook(url, s.telegram_webhook_secret)
        print(f"setWebhook OK -> {url}")
        info = await tg.get_webhook_info()
        print(f"  url                  : {info.get('url')}")
        print(f"  pending_update_count : {info.get('pending_update_count', 0)}")
        print(f"  has_custom_certificate: {info.get('has_custom_certificate')}")
        if info.get("last_error_message"):
            print(f"  last_error           : {info['last_error_message']}")
        return 0
    except TelegramError as e:
        print(f"FAILED: {e}")
        return 1
    finally:
        await tg.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
