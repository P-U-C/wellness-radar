from __future__ import annotations

from datetime import datetime, timezone


def age_hours(value: datetime | None) -> float | None:
    if value is None:
        return None
    normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - normalized).total_seconds() / 3600, 3)


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
