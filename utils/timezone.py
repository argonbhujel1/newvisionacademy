from datetime import datetime
from zoneinfo import ZoneInfo

NEPAL_TZ = ZoneInfo("Asia/Kathmandu")


def now_nepal():
    """Return current datetime in Asia/Kathmandu timezone."""
    return datetime.now(NEPAL_TZ)


def to_nepal(dt):
    """Convert a datetime to Nepal timezone. Assumes naive datetimes are UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(NEPAL_TZ)


def format_date(dt, fmt="%d %B %Y"):
    """Format datetime in Nepal time. Default: 10 August 2026"""
    if dt is None:
        return ""
    local = to_nepal(dt)
    return local.strftime(fmt)


def format_time(dt, fmt="%I:%M %p"):
    """Format time in Nepal time. Default: 10:30 AM"""
    if dt is None:
        return ""
    local = to_nepal(dt)
    return local.strftime(fmt).lstrip("0")


def format_datetime(dt):
    """Full date and time in Nepal time."""
    if dt is None:
        return ""
    return f"{format_date(dt)} {format_time(dt)}"
