from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

CONTACT_TYPES = {"phone", "email", "website", "social"}


def build_contact_method(
    *,
    contact_type: str,
    value: Any,
    source_ref: dict[str, Any],
    confidence: float,
    platform: str | None = None,
) -> dict[str, Any] | None:
    normalized_type = contact_type.strip().lower()
    if normalized_type not in CONTACT_TYPES:
        return None
    if not source_ref or not source_ref.get("source_name"):
        return None
    display_value = normalize_contact_display(normalized_type, value, platform=platform)
    if not display_value:
        return None
    contact: dict[str, Any] = {
        "type": normalized_type,
        "value": display_value,
        "source_ref": source_ref,
        "confidence": max(0.0, min(1.0, float(confidence))),
    }
    if platform:
        contact["platform"] = platform.strip().lower()
    return contact


def normalize_contact_display(
    contact_type: str,
    value: Any,
    *,
    platform: str | None = None,
) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if contact_type == "email":
        email = text.lower()
        return email if _looks_like_email(email) else None
    if contact_type == "phone":
        cleaned = re.sub(r"\s+", " ", text)
        return cleaned if _looks_like_phone(cleaned) else None
    if contact_type == "website":
        return _normalize_url(text)
    if contact_type == "social":
        return _normalize_social(text, platform)
    return None


def normalize_contact_key(contact_type: str, value: Any, *, platform: str | None = None) -> str:
    display = normalize_contact_display(contact_type, value, platform=platform) or str(value or "")
    if contact_type == "phone":
        normalized = re.sub(r"[^0-9+]+", "", display)
        if normalized.startswith("00"):
            return f"+{normalized[2:]}"
        return normalized
    if contact_type == "email":
        return display.lower()
    if contact_type in {"website", "social"}:
        parsed = urlparse(display)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return f"{host}{path}".lower()
    return display.strip().lower()


def merge_contact_methods(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for group in groups:
        for contact in group:
            contact_type = str(contact.get("type") or "").lower()
            value = contact.get("value")
            platform = str(contact.get("platform") or "")
            key = (
                contact_type,
                normalize_contact_key(contact_type, value, platform=platform or None),
                platform,
            )
            if not key[0] or not key[1]:
                continue
            current = merged.get(key)
            if current is None or float(contact.get("confidence") or 0) > float(
                current.get("confidence") or 0
            ):
                merged[key] = contact
    return list(merged.values())


def _looks_like_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))


def _looks_like_phone(value: str) -> bool:
    digits = re.sub(r"\D+", "", value)
    return len(digits) >= 7


def _normalize_url(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("//"):
        text = f"https:{text}"
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, flags=re.IGNORECASE):
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _normalize_social(value: str, platform: str | None) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.lower().startswith(("http://", "https://", "www.")):
        return _normalize_url(text)
    handle = text.removeprefix("@").strip().strip("/")
    if not handle:
        return None
    normalized_platform = (platform or "").lower()
    if normalized_platform == "instagram":
        return f"https://www.instagram.com/{handle}"
    if normalized_platform == "facebook":
        return f"https://www.facebook.com/{handle}"
    return text
