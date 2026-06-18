from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def source_ref(
    *,
    source_name: str,
    url: str | None,
    trust_tier: str,
    source_record_id: str | None,
    licence: str | None,
    seen_at: str | None = None,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "url": url,
        "trust_tier": trust_tier,
        "seen_at": seen_at or utc_now_iso(),
        "source_record_id": source_record_id,
        "licence": licence,
    }
