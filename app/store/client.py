"""Thin PostgREST client for Supabase, using the service role key."""
import httpx

from app.config import Settings


class Store:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._base = f"{settings.supabase_url}/rest/v1"
        self._key = settings.supabase_service_role_key
        self._client = client or httpx.AsyncClient(timeout=15)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    async def insert(self, table: str, row: dict, *, prefer: str = "return=minimal"):
        return await self._client.post(
            f"{self._base}/{table}",
            json=row,
            headers={**self._headers, "Prefer": prefer},
        )

    async def select(self, table: str, params: dict) -> list[dict]:
        r = await self._client.get(
            f"{self._base}/{table}", params=params, headers=self._headers
        )
        r.raise_for_status()
        return r.json()

    async def patch(self, table: str, params: dict, row: dict) -> None:
        r = await self._client.patch(
            f"{self._base}/{table}", params=params, json=row, headers=self._headers
        )
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
