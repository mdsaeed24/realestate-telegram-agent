"""Phase 2 verification - read every tab back through the API and print it."""
from _common import TABS, env, sheets_service


def main():
    e = env()
    svc = sheets_service(e)
    sheet_id = e["GOOGLE_SHEET_ID"]

    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    print(f"sheet : {meta['properties']['title']}")
    print(f"url   : {meta['spreadsheetUrl']}\n")

    result = svc.spreadsheets().values().batchGet(
        spreadsheetId=sheet_id, ranges=[f"{t}!A1:Z100" for t in TABS]
    ).execute()

    ok = True
    for tab, block in zip(TABS, result["valueRanges"]):
        rows = block.get("values", [])
        header, data = (rows[0], rows[1:]) if rows else ([], [])
        print(f"=== {tab} === ({len(data)} data rows)")
        if header != TABS[tab]:
            print(f"  !! header mismatch\n     want: {TABS[tab]}\n     got : {header}")
            ok = False
        for r in data:
            cells = dict(zip(header, r))
            if tab == "Properties":
                media = cells.get("media_folder") or "(no media)"
                print(f"  {cells['property_id']}  {cells['name']:<24} "
                      f"{cells['property_type']:<6} Rs {int(cells['price_inr']):>10,}  "
                      f"{cells['locality']:<28} {media}")
            elif tab == "Leads":
                print(f"  {cells['lead_id']}  {cells['name']:<14} {cells['status']:<6} "
                      f"{cells['deep_link']}")
            else:
                print("  " + " | ".join(r))
        if not data:
            print("  (empty - headers only)")
        print()

    print("HEADERS OK" if ok else "HEADERS MISMATCHED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
