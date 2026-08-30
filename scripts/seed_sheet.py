"""Phase 2 - create the three tabs, write headers, seed rows, mint deep-link tokens.

Idempotent: re-running rewrites the same rows rather than appending duplicates.

Seed property rows are PLACEHOLDER data for the client to replace, with one
exception: PROP-001 (Sobha Magnolia) is the only property with media, and its
filenames are the real contents of the Supabase bucket. The other four
deliberately have a blank media_folder - a listing with no media is normal
behaviour, not an error.
"""
import secrets

import httpx

from _common import TABS, env, sheets_service

MAPS = "https://www.google.com/maps/search/?api=1&query="

PROPERTIES = [
    # The one real property: filenames verified against the bucket 2026-08-28.
    ["PROP-001", "Sobha Magnolia", "3BHK", 20000000,
     "Bengaluru-Mysuru Expressway", "Bengaluru", "active",
     "Ready to move\n1,650 sq ft\nEast facing\nClubhouse and pool\n2 covered parking",
     MAPS + "Sobha+Magnolia+Bengaluru",
     "Sobha Magnolia", "Hero.png", "Image 1.png|Image 2.png|Image3.png", ""],
    # Placeholder rows - no media folder.
    ["PROP-002", "Lakeview Enclave", "3BHK", 24500000,
     "Whitefield", "Bengaluru", "active",
     "Under construction, possession Dec 2027\n1,820 sq ft\nLake facing\nGym and clubhouse",
     MAPS + "Whitefield+Bengaluru", "", "", "", ""],
    ["PROP-003", "Green Meadows", "2BHK", 13500000,
     "Varthur", "Bengaluru", "active",
     "Ready to move\n1,150 sq ft\nGated community\n1 covered parking",
     MAPS + "Varthur+Bengaluru", "", "", "", ""],
    ["PROP-004", "Riverbend Residences", "3BHK", 18500000,
     "Bengaluru-Mysuru Expressway", "Bengaluru", "active",
     "Possession Jun 2027\n1,700 sq ft\nCorner unit\nChildren's play area",
     MAPS + "Bengaluru+Mysuru+Expressway", "", "", "", ""],
    ["PROP-005", "Sunridge Villas", "Villa", 42000000,
     "Kanakapura Road", "Bengaluru", "active",
     "Ready to move\n3,200 sq ft\nPrivate garden\n4 car parking\nSolar backup",
     MAPS + "Kanakapura+Road+Bengaluru", "", "", "", ""],
]

LEADS = [
    ["LEAD-001", "Anita Rao",     "+919845012345", "website",   "PROP-001", "new", ""],
    ["LEAD-002", "Vikram Shetty", "+919845023456", "instagram", "PROP-004", "new", ""],
    ["LEAD-003", "Priya Nair",    "+919845034567", "referral",  "PROP-003", "new", ""],
]


def ensure_tabs(svc, sheet_id):
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    requests = []

    # Reuse the default empty tab as Properties rather than leaving it orphaned.
    if "Properties" not in existing and "Sheet1" in existing:
        requests.append({"updateSheetProperties": {
            "properties": {"sheetId": existing["Sheet1"], "title": "Properties"},
            "fields": "title"}})
        existing["Properties"] = existing.pop("Sheet1")

    for title in TABS:
        if title not in existing:
            requests.append({"addSheet": {"properties": {"title": title}}})

    if requests:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body={"requests": requests}).execute()
    return [s["properties"]["title"]
            for s in svc.spreadsheets().get(spreadsheetId=sheet_id).execute()["sheets"]]


def write(svc, sheet_id, tab, headers, rows):
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        body={"values": [headers] + rows},
    ).execute()


def store_tokens(e, pairs):
    """Upsert deep-link tokens into Supabase via PostgREST."""
    key = e["SUPABASE_SERVICE_ROLE_KEY"]
    r = httpx.post(
        e["SUPABASE_URL"].rstrip("/") + "/rest/v1/deep_link_tokens",
        json=[{"token": t, "lead_id": lid} for lid, t in pairs],
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.status_code


def main():
    e = env()
    sheet_id = e["GOOGLE_SHEET_ID"]
    svc = sheets_service(e)

    print("tabs:", ensure_tabs(svc, sheet_id))

    # Mint one token per lead; the bot username is unknown until Phase 3, so the
    # deep link is written with a placeholder that Phase 4 substitutes.
    pairs = [(row[0], secrets.token_urlsafe(16)) for row in LEADS]
    for row, (_, token) in zip(LEADS, pairs):
        row[6] = f"https://t.me/<BOT_USERNAME>?start={token}"

    write(svc, sheet_id, "Properties", TABS["Properties"], PROPERTIES)
    write(svc, sheet_id, "Leads", TABS["Leads"], LEADS)
    write(svc, sheet_id, "Bookings", TABS["Bookings"], [])
    print(f"wrote {len(PROPERTIES)} properties, {len(LEADS)} leads, Bookings headers")

    print("supabase deep_link_tokens upsert:", store_tokens(e, pairs))


if __name__ == "__main__":
    main()
