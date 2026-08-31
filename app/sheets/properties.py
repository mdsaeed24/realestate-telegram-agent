"""Property rows. media_folder is its own field and is never derived from the
property id, so adding media later is a data change, not a code change."""
from dataclasses import dataclass, field

from app.sheets.client import Sheets

TAB = "Properties"


@dataclass(frozen=True)
class Property:
    property_id: str
    name: str
    property_type: str
    price_inr: int
    locality: str
    city: str
    status: str
    key_details: str
    maps_url: str
    media_folder: str
    hero_file: str
    gallery_files: list[str] = field(default_factory=list)
    video_file: str = ""

    @property
    def has_media(self) -> bool:
        return bool(self.media_folder and self.hero_file)

    @property
    def has_gallery(self) -> bool:
        return bool(self.gallery_files)

    @property
    def has_video(self) -> bool:
        return bool(self.media_folder and self.video_file)

    @property
    def bullets(self) -> list[str]:
        return [b.strip() for b in self.key_details.splitlines() if b.strip()]


def _int(value: str) -> int:
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0


def parse(row: dict) -> Property:
    return Property(
        property_id=row.get("property_id", "").strip(),
        name=row.get("name", "").strip(),
        property_type=row.get("property_type", "").strip(),
        price_inr=_int(row.get("price_inr", "")),
        locality=row.get("locality", "").strip(),
        city=row.get("city", "").strip(),
        status=(row.get("status") or "active").strip().lower(),
        key_details=row.get("key_details", ""),
        maps_url=row.get("maps_url", "").strip(),
        media_folder=row.get("media_folder", "").strip(),
        hero_file=row.get("hero_file", "").strip(),
        gallery_files=[f.strip() for f in row.get("gallery_files", "").split("|") if f.strip()],
        video_file=row.get("video_file", "").strip(),
    )


async def load_active(sheets: Sheets) -> list[Property]:
    """Only active rows are ever shown to a lead."""
    rows = await sheets.read(TAB)
    props = [parse(r) for r in rows if r.get("property_id")]
    return [p for p in props if p.status == "active"]
