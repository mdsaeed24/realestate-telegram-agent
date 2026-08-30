"""Environment configuration. Fails loudly at import time on a missing required var."""
import os
import pathlib
from dataclasses import dataclass

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    google_sheet_id: str
    google_credentials_path: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    # Deferred until the model is chosen; see BUILD_SPEC Phase 5.
    anthropic_api_key: str = ""
    anthropic_model: str = ""

    @property
    def telegram_api(self) -> str:
        return f"https://api.telegram.org/bot{self.telegram_bot_token}"


REQUIRED = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GOOGLE_SHEET_ID",
    "GOOGLE_CREDENTIALS_PATH",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
)


def _clean(name: str) -> str:
    """Read a var and reject whitespace damage from copy-paste.

    A bot token pasted with a line break or a space after the colon authenticates
    nowhere and produces a 401 that looks like a wrong token, so catch it here.
    """
    raw = os.getenv(name)
    if raw is None:
        return ""
    if raw != raw.strip():
        raise ConfigError(f"{name} has leading/trailing whitespace - remove it")
    if any(c.isspace() for c in raw):
        raise ConfigError(
            f"{name} contains a space or line break. It must be one unbroken value."
        )
    return raw


def load(env_file: str | pathlib.Path | None = None) -> Settings:
    load_dotenv(env_file or ROOT / ".env")
    values = {name: _clean(name) for name in REQUIRED}
    missing = [n for n, v in values.items() if not v]
    if missing:
        raise ConfigError(f"missing required env vars: {', '.join(missing)}")

    token = values["TELEGRAM_BOT_TOKEN"]
    if ":" not in token or not token.split(":", 1)[0].isdigit():
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN must look like <digits>:<secret> as issued by BotFather"
        )

    return Settings(
        supabase_url=values["SUPABASE_URL"].rstrip("/"),
        supabase_service_role_key=values["SUPABASE_SERVICE_ROLE_KEY"],
        google_sheet_id=values["GOOGLE_SHEET_ID"],
        google_credentials_path=values["GOOGLE_CREDENTIALS_PATH"],
        telegram_bot_token=token,
        telegram_webhook_secret=values["TELEGRAM_WEBHOOK_SECRET"],
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", ""),
    )
