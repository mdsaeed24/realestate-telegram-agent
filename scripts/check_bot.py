"""Verify the bot token works and report the bot's identity and webhook state.

Prints no secret material.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.config import load  # noqa: E402
from app.telegram.client import Telegram, TelegramError  # noqa: E402


async def main() -> int:
    s = load()
    tg = Telegram(s)
    try:
        me = await tg.get_me()
        print("getMe OK")
        print(f"  id       : {me['id']}")
        print(f"  username : @{me['username']}")
        print(f"  name     : {me.get('first_name')}")

        info = await tg.get_webhook_info()
        print("\ngetWebhookInfo")
        print(f"  url                  : {info.get('url') or '(none set)'}")
        print(f"  pending_update_count : {info.get('pending_update_count', 0)}")
        if info.get("last_error_message"):
            print(f"  last_error           : {info['last_error_message']}")
        return 0
    except TelegramError as e:
        print(f"FAILED: {e}")
        if e.code == 401:
            print("  401 means the token is not valid - check it was copied whole.")
        return 1
    finally:
        await tg.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
