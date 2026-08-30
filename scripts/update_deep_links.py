"""Replace the <BOT_USERNAME> placeholder in the Leads tab with the real username.

Phase 2 mints the tokens before the bot exists, so the links are written with a
placeholder. This fills it in, and is safe to re-run.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from _common import LEAD_HEADERS, env, sheets_service  # noqa: E402
from app.config import load  # noqa: E402
from app.telegram.client import Telegram  # noqa: E402

PLACEHOLDER = "<BOT_USERNAME>"


async def bot_username() -> str:
    tg = Telegram(load())
    try:
        return (await tg.get_me())["username"]
    finally:
        await tg.aclose()


def main() -> int:
    username = asyncio.run(bot_username())
    e = env()
    svc = sheets_service(e)
    sid = e["GOOGLE_SHEET_ID"]

    rows = svc.spreadsheets().values().get(
        spreadsheetId=sid, range="Leads!A1:Z100"
    ).execute().get("values", [])
    if not rows:
        print("Leads tab is empty")
        return 1

    header, data = rows[0], rows[1:]
    col = header.index("deep_link")
    changed = 0
    for r in data:
        while len(r) <= col:
            r.append("")
        if PLACEHOLDER in r[col]:
            r[col] = r[col].replace(PLACEHOLDER, username)
            changed += 1

    svc.spreadsheets().values().update(
        spreadsheetId=sid, range="Leads!A1", valueInputOption="RAW",
        body={"values": [header] + data},
    ).execute()

    print(f"bot username: @{username}")
    print(f"links updated: {changed}")
    for r in data:
        print(f"  {r[0]:<9} {r[1]:<14} {r[col]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
