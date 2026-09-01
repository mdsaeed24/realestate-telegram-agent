"""Google Sheets access. Property and lead rows are read live so the client's
edits take effect immediately (BUILD_SPEC section 7)."""
import asyncio
from functools import lru_cache

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import ROOT, Settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@lru_cache(maxsize=1)
def _service(credentials_path: str):
    creds = Credentials.from_service_account_file(
        str(ROOT / credentials_path), scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


class Sheets:
    def __init__(self, settings: Settings):
        self._sheet_id = settings.google_sheet_id
        self._path = settings.google_credentials_path

    def _read_sync(self, tab: str) -> list[dict]:
        rows = (
            _service(self._path)
            .spreadsheets()
            .values()
            .get(spreadsheetId=self._sheet_id, range=f"{tab}!A1:Z1000")
            .execute()
            .get("values", [])
        )
        if not rows:
            return []
        header, data = rows[0], rows[1:]
        out = []
        for r in data:
            padded = list(r) + [""] * (len(header) - len(r))
            out.append(dict(zip(header, padded)))
        return out

    async def read(self, tab: str) -> list[dict]:
        return await asyncio.to_thread(self._read_sync, tab)

    def _append_sync(self, tab: str, row: list) -> None:
        _service(self._path).spreadsheets().values().append(
            spreadsheetId=self._sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    async def append(self, tab: str, row: list) -> None:
        await asyncio.to_thread(self._append_sync, tab, row)

    def _update_sync(self, rng: str, values: list[list]) -> None:
        _service(self._path).spreadsheets().values().update(
            spreadsheetId=self._sheet_id, range=rng,
            valueInputOption="RAW", body={"values": values},
        ).execute()

    async def update_range(self, rng: str, values: list[list]) -> None:
        await asyncio.to_thread(self._update_sync, rng, values)

    def _clear_sync(self, rng: str) -> None:
        _service(self._path).spreadsheets().values().clear(
            spreadsheetId=self._sheet_id, range=rng, body={}).execute()

    async def clear(self, rng: str) -> None:
        await asyncio.to_thread(self._clear_sync, rng)
