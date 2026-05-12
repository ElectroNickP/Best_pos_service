"""
POS Service — Settings Service.
Manages dynamic key-value configuration stored in the database.
Falls back to config.py (.env) values when no DB override exists.
"""
from sqlalchemy import select
from loguru import logger

from models import AsyncSessionLocal, POSSetting
from config import config


# Default settings with descriptions (seeded on first run)
DEFAULT_SETTINGS = {
    "STORE_SPREADSHEET_ID": {
        "value": config.STORE_SPREADSHEET_ID,
        "description": "Google Sheets ID for the store price list",
    },
    "PIER_NAME": {
        "value": config.PIER_NAME,
        "description": "Default pier name for this POS instance",
    },
    "NSPK_SLUG": {
        "value": config.NSPK_SLUG,
        "description": "NSPK payment gateway slug",
    },
    "NSPK_POINT_ID": {
        "value": str(config.NSPK_POINT_ID),
        "description": "NSPK payment gateway point ID",
    },
    "TELEGRAM_LOG_CHAT_ID": {
        "value": "-1003556020066",
        "description": "Telegram chat ID for sale notifications",
    },
    "TELEGRAM_LOG_TOPIC_ID": {
        "value": "569",
        "description": "Telegram topic ID within the log chat",
    },
}


class SettingsService:

    async def seed_defaults(self):
        """Seed default settings if they don't exist in DB yet."""
        async with AsyncSessionLocal() as session:
            for key, info in DEFAULT_SETTINGS.items():
                existing = await session.execute(
                    select(POSSetting).where(POSSetting.key == key)
                )
                if not existing.scalars().first():
                    setting = POSSetting(
                        key=key,
                        value=info["value"],
                        description=info["description"],
                    )
                    session.add(setting)
                    logger.debug(f"Seeded setting: {key} = {info['value']}")
            await session.commit()
        logger.info("Settings seeded (new keys only).")

    async def get_all(self) -> list[dict]:
        """Get all settings as a list of dicts."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(POSSetting).order_by(POSSetting.key))
            settings = result.scalars().all()
            return [
                {
                    "key": s.key,
                    "value": s.value,
                    "description": s.description,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in settings
            ]

    async def get(self, key: str, default: str = "") -> str:
        """Get a single setting value by key. Falls back to default."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(POSSetting).where(POSSetting.key == key)
            )
            setting = result.scalars().first()
            if setting:
                return setting.value
            return default

    async def set(self, key: str, value: str, description: str | None = None) -> dict:
        """Set a setting value. Creates if not exists, updates if exists."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(POSSetting).where(POSSetting.key == key)
            )
            setting = result.scalars().first()

            if setting:
                setting.value = value
                if description is not None:
                    setting.description = description
            else:
                setting = POSSetting(
                    key=key,
                    value=value,
                    description=description or "",
                )
                session.add(setting)

            await session.commit()
            await session.refresh(setting)
            logger.info(f"Setting updated: {key} = {value}")
            return {
                "key": setting.key,
                "value": setting.value,
                "description": setting.description,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
            }

    async def delete(self, key: str) -> bool:
        """Delete a setting by key."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(POSSetting).where(POSSetting.key == key)
            )
            setting = result.scalars().first()
            if setting:
                await session.delete(setting)
                await session.commit()
                logger.info(f"Setting deleted: {key}")
                return True
            return False


# Singleton
settings_service = SettingsService()
