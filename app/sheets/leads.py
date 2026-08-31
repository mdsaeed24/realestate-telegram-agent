"""Lead rows, keyed by the stable lead_id column the client never edits."""
from dataclasses import dataclass

from app.sheets.client import Sheets

TAB = "Leads"


@dataclass(frozen=True)
class Lead:
    lead_id: str
    name: str
    phone: str
    source: str
    enquired_about: str
    status: str
    deep_link: str


def parse(row: dict) -> Lead:
    return Lead(
        lead_id=row.get("lead_id", "").strip(),
        name=row.get("name", "").strip(),
        phone=row.get("phone", "").strip(),
        source=row.get("source", "").strip(),
        enquired_about=row.get("enquired_about", "").strip(),
        status=(row.get("status") or "new").strip().lower(),
        deep_link=row.get("deep_link", "").strip(),
    )


async def by_id(sheets: Sheets, lead_id: str) -> Lead | None:
    for row in await sheets.read(TAB):
        if row.get("lead_id", "").strip() == lead_id:
            return parse(row)
    return None
