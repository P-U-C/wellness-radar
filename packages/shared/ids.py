from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def stable_id(prefix: str, *parts: object, max_len: int = 96) -> str:
    clean_parts = [slugify(str(part)) for part in parts if part is not None and str(part)]
    base = "_".join([prefix, *clean_parts]).strip("_")
    if len(base) <= max_len:
        return base
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"{base[: max_len - 13]}_{digest}"


def content_hash(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
