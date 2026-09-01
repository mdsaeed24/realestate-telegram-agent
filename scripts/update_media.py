"""Point each property row at its media folder, hero and gallery.

Reads what is actually in the bucket rather than assuming a naming scheme -
the filenames are inconsistent, and media_folder is its own field precisely so
that adding media stays a data change.

AVIF is excluded: Telegram's sendPhoto rejects it ("failed to get HTTP URL
content"), verified against the live API.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import httpx  # noqa: E402

from _common import PROPERTY_HEADERS, env, sheets_service  # noqa: E402
from app.config import load  # noqa: E402

BUCKET = "Property media"
SENDABLE = (".jpg", ".jpeg", ".png", ".webp")   # .avif is rejected by Telegram

# Which bucket folder belongs to which property, and which file leads.
# The folder name is not derived from the property name - "Riverbed Residency"
# in the bucket is "Riverbend Residences" in the sheet.
MEDIA = {
    "PROP-001": ("Sobha Magnolia",     "Sobha Living.jpg"),
    "PROP-002": ("Lakeview Enclave",   "lakeview living.jpg"),
    "PROP-003": ("Green Meadows",      "Green Meadows Living .jpg"),
    "PROP-004": ("Riverbed Residency", "Riverbed living.jpg"),
    "PROP-005": ("Sunridge Villas",    "Hero.png"),
}


def list_folder(settings, folder: str) -> list[str]:
    r = httpx.post(
        f"{settings.supabase_url}/storage/v1/object/list/{BUCKET}",
        json={"prefix": f"{folder}/", "limit": 200, "sortBy": {"column": "name", "order": "asc"}},
        headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"},
        timeout=60,
    )
    r.raise_for_status()
    return [o["name"] for o in r.json() if o.get("name")]


def main() -> int:
    settings = load()
    e = env()
    svc = sheets_service(e)
    sid = e["GOOGLE_SHEET_ID"]

    rows = svc.spreadsheets().values().get(
        spreadsheetId=sid, range="Properties!A1:Z100").execute().get("values", [])
    header, data = rows[0], rows[1:]
    idx = {h: header.index(h) for h in PROPERTY_HEADERS}

    for row in data:
        while len(row) < len(header):
            row.append("")
        pid = row[idx["property_id"]]
        if pid not in MEDIA:
            continue
        folder, hero = MEDIA[pid]

        files = list_folder(settings, folder)
        usable = [f for f in files if f.lower().endswith(SENDABLE)]
        gallery = [f for f in usable if f != hero]
        skipped = [f for f in files if f not in usable]

        row[idx["media_folder"]] = folder
        row[idx["hero_file"]] = hero
        row[idx["gallery_files"]] = "|".join(gallery)

        print(f"{pid}  {folder}")
        print(f"    hero    : {hero}")
        print(f"    gallery : {len(gallery)} -> {', '.join(gallery)}")
        if skipped:
            print(f"    SKIPPED : {', '.join(skipped)}  (Telegram cannot send these)")

    svc.spreadsheets().values().update(
        spreadsheetId=sid, range="Properties!A1", valueInputOption="RAW",
        body={"values": [header] + data},
    ).execute()
    print("\nsheet updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
