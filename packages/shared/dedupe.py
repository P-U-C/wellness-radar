from __future__ import annotations


def choose_best_name(primary: str | None, fallback: str | None) -> str:
    if primary and primary.strip():
        return primary.strip()
    if fallback and fallback.strip():
        return fallback.strip()
    return "Unknown operator"
