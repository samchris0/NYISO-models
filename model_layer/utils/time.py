from datetime import datetime
from zoneinfo import ZoneInfo


NYISO_TIMEZONE = ZoneInfo("America/New_York")


def now_ny() -> datetime:
    """Return the current timezone-aware New York time."""
    return datetime.now(NYISO_TIMEZONE)


def as_ny_datetime(value: datetime) -> datetime:
    """Normalize an aware datetime to New York; interpret naive values as NY time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=NYISO_TIMEZONE)
    return value.astimezone(NYISO_TIMEZONE)


def floor_to_five_minutes(value: datetime) -> datetime:
    """Floor a datetime to its New York five-minute boundary."""
    value = as_ny_datetime(value)
    return value.replace(
        minute=(value.minute // 5) * 5,
        second=0,
        microsecond=0,
    )
