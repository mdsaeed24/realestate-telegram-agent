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
            # Appended rows can be shorter than the header; pad so trailing
            # columns are present-but-empty rather than missing.
            padded = list(r) + [""] * (len(header) - len(r))
            cells = dict(zip(header, padded))
            if tab == "Properties":
                media = cells.get("media_folder") or "(no media)"
                print(f"  {cells['property_id']}  {cells['name']:<24} "
                      f"{cells['property_type']:<6} Rs {int(cells['price_inr']):>10,}  "
                      f"{cells['locality']:<28} {media}")
            elif tab == "Leads":
                phone = cells.get("phone", "") or "-"
                link = cells.get("deep_link", "") or "(self-identified)"
                print(f"  {cells['lead_id']:<12} {cells['name']:<14} {phone:<15} "
                      f"{cells['status']:<6} {link}")
            else:
                print("  " + " | ".join(r))
        if not data:
            print("  (empty - headers only)")
        print()

    print("HEADERS OK" if ok else "HEADERS MISMATCHED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
