"""Phase 1 verification - config rejects the copy-paste damage that causes 401s."""
import pytest

from app.config import ConfigError, load

GOOD = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-key",
    "GOOGLE_SHEET_ID": "sheet-id",
    "GOOGLE_CREDENTIALS_PATH": "credentials.json",
    "TELEGRAM_BOT_TOKEN": "8572689045:AAHwFakeTokenForTests",
    "TELEGRAM_WEBHOOK_SECRET": "secret",
}


def apply(monkeypatch, overrides=None, drop=()):
    for k, v in {**GOOD, **(overrides or {})}.items():
        if k not in drop:
            monkeypatch.setenv(k, v)
    for k in drop:
        monkeypatch.delenv(k, raising=False)
    # Stop a real .env on disk from satisfying anything we deliberately removed.
    monkeypatch.setattr("app.config.load_dotenv", lambda *a, **k: None)


def test_loads_a_clean_environment(monkeypatch):
    apply(monkeypatch)
    s = load()
    assert s.telegram_bot_token == GOOD["TELEGRAM_BOT_TOKEN"]
    assert s.telegram_api.endswith(GOOD["TELEGRAM_BOT_TOKEN"])


def test_trailing_slash_stripped_from_supabase_url(monkeypatch):
    apply(monkeypatch, {"SUPABASE_URL": "https://example.supabase.co/"})
    assert load().supabase_url == "https://example.supabase.co"


def test_missing_var_is_named(monkeypatch):
    apply(monkeypatch, drop=["TELEGRAM_WEBHOOK_SECRET"])
    with pytest.raises(ConfigError, match="TELEGRAM_WEBHOOK_SECRET"):
        load()


@pytest.mark.parametrize(
    "bad",
    [
        "8572689045: AAHwFakeTokenForTests",   # space after the colon
        "8572689045:AAHwFake\nTokenForTests",  # wrapped across lines
        " 8572689045:AAHwFakeTokenForTests",   # leading space
    ],
)
def test_whitespace_damaged_token_is_rejected(monkeypatch, bad):
    """A token pasted with a break 401s in a way that looks like a wrong token."""
    apply(monkeypatch, {"TELEGRAM_BOT_TOKEN": bad})
    with pytest.raises(ConfigError):
        load()


def test_token_must_have_botfather_shape(monkeypatch):
    apply(monkeypatch, {"TELEGRAM_BOT_TOKEN": "not-a-real-token"})
    with pytest.raises(ConfigError, match="BotFather"):
        load()
