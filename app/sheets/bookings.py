"""Mirror confirmed bookings into the sheet so the sales team sees them where
they already work. Supabase remains the system of record."""
from app.sheets.client import Sheets

TAB = "Bookings"

HEADERS = [
    "booking_id", "lead_id", "lead_name", "property_id", "property_name",
    "slot_date", "slot_time", "maps_url", "created_at",
]


async def append(sheets: Sheets, **row) -> None:
    await sheets.append(TAB, [str(row.get(h, "")) for h in HEADERS])
