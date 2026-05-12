"""
POS Service — Time Utilities.
Centralized timezone handling for Phuket (Asia/Bangkok, UTC+7).
"""
import datetime
import zoneinfo
import re
from loguru import logger

PHUKET_TZ = zoneinfo.ZoneInfo("Asia/Bangkok")


def get_phuket_now() -> datetime.datetime:
    """Returns the current datetime in Phuket timezone (UTC+7)."""
    return datetime.datetime.now(PHUKET_TZ)


def get_phuket_today() -> datetime.date:
    """Returns the current date in Phuket timezone."""
    return get_phuket_now().date()


def get_day_bounds(date: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    """Returns timezone-aware start and end of a given date in Phuket time."""
    day_start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=PHUKET_TZ)
    day_end = day_start + datetime.timedelta(days=1)
    return day_start, day_end


def is_time_format(s: str) -> bool:
    """Checks if a string is in HH:MM format."""
    if not s:
        return False
    return bool(re.match(r'^\d{1,2}:\d{2}$', s.strip()))


def to_phuket_time(dt: datetime.datetime) -> datetime.datetime:
    """Converts a datetime to Phuket timezone (Asia/Bangkok)."""
    if not dt:
        return dt
    
    original = dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    
    result = dt.astimezone(PHUKET_TZ)
    logger.info(f"Time conversion: {original} (naive? {original.tzinfo is None}) -> {result}")
    return result
