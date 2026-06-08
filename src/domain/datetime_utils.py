from datetime import datetime
from zoneinfo import ZoneInfo

ART = ZoneInfo("America/Argentina/Buenos_Aires")


def to_art(dt: datetime) -> datetime:
    """Convert a datetime to Argentina local time (ART, UTC-3).

    MercadoPago often returns timestamps with a ``-04:00`` offset even though
    Argentina no longer observes DST and is permanently UTC-3. Converting to ART
    preserves the correct instant and fixes the displayed local hour.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ART)

    return dt.astimezone(ART)


def parse_mp_datetime(value: str | datetime) -> datetime:
    """Parse a MercadoPago timestamp and normalize it to ART."""
    if isinstance(value, datetime):
        return to_art(value)

    normalized = value.replace("Z", "+00:00")
    return to_art(datetime.fromisoformat(normalized))
