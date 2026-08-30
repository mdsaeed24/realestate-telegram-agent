"""Phase 3 verification - the webhook acks fast, rejects bad secrets, and is
idempotent when Telegram redelivers an update."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.store.client import Store

SETTINGS = Settings(
    supabase_url="https://example.supabase.co",
    supabase_service_role_key="service-key",
    google_sheet_id="sheet-id",
    google_credentials_path="credentials.json",
    telegram_bot_token="8572689045:AAHwFakeTokenForTests",
    telegram_webhook_secret="test-secret",
)

UPDATE = {
    "update_id": 100001,
    "message": {"message_id": 5, "chat": {"id": 4242}, "text": "hi"},
}


class FakePostgrest:
    """Stands in for Supabase, enforcing the processed_updates primary key."""

    def __init__(self):
        self.seen: set[int] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/processed_updates"):
            import json

            update_id = json.loads(request.content)["update_id"]
            if update_id in self.seen:
                return httpx.Response(
                    409,
                    json={"code": "23505", "message": "duplicate key value"},
                )
            self.seen.add(update_id)
            return httpx.Response(201)
        return httpx.Response(200, json=[])


@pytest.fixture
def client(monkeypatch):
    from app import main

    fake = FakePostgrest()
    transport = httpx.MockTransport(fake.handler)

    main.app.state.settings = SETTINGS
    main.app.state.store = Store(SETTINGS, client=httpx.AsyncClient(transport=transport))
    main.app.state.telegram = None
    main.app.state.configured = True

    with TestClient(main.app) as c:
        c.fake = fake
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_bad_secret_token_is_rejected(client):
    r = client.post(
        "/webhook/telegram",
        json=UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert r.status_code == 403
    assert client.fake.seen == set(), "a rejected call must not touch the database"


def test_missing_secret_token_is_rejected(client):
    assert client.post("/webhook/telegram", json=UPDATE).status_code == 403


def test_update_is_processed_once(client):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
    first = client.post("/webhook/telegram", json=UPDATE, headers=headers)
    assert first.status_code == 200
    assert client.fake.seen == {100001}


def test_redelivered_update_is_not_processed_twice(client):
    """Telegram retries on a slow ack; the second delivery must be a no-op."""
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
    for _ in range(3):
        r = client.post("/webhook/telegram", json=UPDATE, headers=headers)
        assert r.status_code == 200, "a duplicate must still ack 200"
    assert client.fake.seen == {100001}, "claimed exactly once across 3 deliveries"


def test_distinct_updates_are_each_processed(client):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
    for uid in (200001, 200002):
        client.post("/webhook/telegram", json={**UPDATE, "update_id": uid}, headers=headers)
    assert client.fake.seen == {200001, 200002}


def test_update_without_id_is_ignored(client):
    headers = {"X-Telegram-Bot-Api-Secret-Token": "test-secret"}
    r = client.post("/webhook/telegram", json={"message": {}}, headers=headers)
    assert r.status_code == 200
    assert client.fake.seen == set()
