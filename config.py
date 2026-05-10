"""
POS Service Configuration.
All settings are loaded from environment variables or .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import SecretStr
from typing import Optional


class Settings(BaseSettings):
    # ── Server ──
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # ── Security ──
    API_KEY: SecretStr  # Shared secret for service-to-service auth (bot → POS)
    BOT_TOKENS: str = ""  # Comma-separated Telegram bot tokens for initData validation
    BOT_WEBHOOK_URL: Optional[str] = None  # URL of the bot's webhook receiver (e.g. http://bot:8080/api/webhook/payment)

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://pos_user:pos_password@localhost:5432/pos_db"

    # ── Google Sheets ──
    STORE_SPREADSHEET_ID: str = ""
    GOOGLE_SA_PATH: str = "google_service_account/"

    # ── NSPK Payment Gateway ──
    NSPK_SLUG: str = "perm_52edadbda3b3c235bad91e9e76025d4c"
    NSPK_POINT_ID: int = 261

    # ── Pier Identity (which pier this POS instance serves) ──
    PIER_NAME: str = "Default"  # e.g. "Yamu", "RPM", "Chalong"

    # ── Timezone ──
    TIMEZONE: str = "Asia/Bangkok"

    # ── CORS ──
    CORS_ORIGINS: str = "*"  # Comma-separated origins, or "*" for dev

    @property
    def bot_token_list(self) -> list[str]:
        """Parse comma-separated bot tokens for multi-bot initData validation."""
        if not self.BOT_TOKENS:
            return []
        return [t.strip() for t in self.BOT_TOKENS.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        origins = self.CORS_ORIGINS.strip()
        if origins == "*":
            return ["*"]
        return [o.strip() for o in origins.split(",") if o.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


config = Settings()
