"""Telegram Bot API client.

Media senders take a URL or bytes and send directly to the user - they never
return a URL to the model, because the model cannot guarantee message ordering
and out-of-order media breaks the conversation (CLAUDE.md).
"""
import httpx

from app.config import Settings


class TelegramError(RuntimeError):
    def __init__(self, method: str, description: str, code: int):
        super().__init__(f"{method} failed [{code}]: {description}")
        self.method = method
        self.description = description
        self.code = code

    @property
    def is_stale_file_id(self) -> bool:
        """Telegram's signal that a cached file_id is no longer usable."""
        d = self.description.lower()
        return "wrong file identifier" in d or "wrong remote file id" in d


class Telegram:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._base = settings.telegram_api
        self._client = client or httpx.AsyncClient(timeout=30)

    async def _call(self, method: str, payload: dict) -> dict:
        r = await self._client.post(f"{self._base}/{method}", json=payload)
        body = r.json()
        if not body.get("ok"):
            raise TelegramError(
                method, body.get("description", "unknown"), body.get("error_code", r.status_code)
            )
        return body["result"]

    async def send_message(self, chat_id: int, text: str) -> dict:
        return await self._call("sendMessage", {"chat_id": chat_id, "text": text})

    async def send_photo(self, chat_id: int, photo: str, caption: str | None = None) -> dict:
        payload = {"chat_id": chat_id, "photo": photo}
        if caption:
            payload["caption"] = caption
        return await self._call("sendPhoto", payload)

    async def send_media_group(self, chat_id: int, media: list[dict]) -> list[dict]:
        return await self._call("sendMediaGroup", {"chat_id": chat_id, "media": media})

    async def send_video(self, chat_id: int, video: str, caption: str | None = None) -> dict:
        payload = {"chat_id": chat_id, "video": video, "supports_streaming": True}
        if caption:
            payload["caption"] = caption
        return await self._call("sendVideo", payload)

    async def get_me(self) -> dict:
        return await self._call("getMe", {})

    async def get_webhook_info(self) -> dict:
        return await self._call("getWebhookInfo", {})

    async def set_webhook(self, url: str, secret_token: str) -> dict:
        return await self._call(
            "setWebhook",
            {"url": url, "secret_token": secret_token, "drop_pending_updates": False},
        )

    async def aclose(self) -> None:
        await self._client.aclose()
