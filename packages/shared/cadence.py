from __future__ import annotations

import os
import re
from collections.abc import Mapping

SECONDS_PER_DAY = 24 * 60 * 60

DEFAULT_CADENCE_INTERVAL_SECONDS = {
    "15_min": 15 * 60,
    "hourly": 60 * 60,
    "daily": SECONDS_PER_DAY,
    "weekdays": SECONDS_PER_DAY,
    "weekly": 7 * SECONDS_PER_DAY,
    "annual": 365 * SECONDS_PER_DAY,
    "as_published": SECONDS_PER_DAY,
    "as_released": SECONDS_PER_DAY,
}

DISABLED_AUTO_CADENCE_TOKENS = {"manual", "fixture"}

DEFAULT_CADENCE_SLA_HOURS = {
    "15_min": 24,
    "hourly": 24,
    "daily": 36,
    "weekdays": 36,
    "weekly": 24 * 8,
    "annual": 24 * 400,
    "as_published": 36,
    "as_released": 36,
}

DISABLED_AUTO_CADENCE_SLA_HOURS = 24 * 90
UNKNOWN_CADENCE_SLA_HOURS = 24 * 14


def cadence_tokens(cadence: str) -> list[str]:
    normalized = cadence.lower().replace("-", "_")
    return [token for token in re.split(r"[^a-z0-9_]+", normalized) if token]


def env_key_for_cadence(token: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", token.upper()).strip("_")
    return f"WR_SCHED_{normalized}_SECONDS"


def interval_seconds_for_cadence(
    cadence: str,
    env: Mapping[str, str] | None = None,
) -> int | None:
    tokens = cadence_tokens(cadence)
    if not tokens or DISABLED_AUTO_CADENCE_TOKENS.intersection(tokens):
        return None

    values = env or os.environ
    exact_key = env_key_for_cadence("_".join(tokens))
    exact_value = _positive_int_or_none(values.get(exact_key))
    if exact_value is not None:
        return exact_value

    intervals: list[int] = []
    for token in tokens:
        interval = _interval_for_token(token, values)
        if interval is not None:
            intervals.append(interval)
    if not intervals:
        return None
    return min(intervals)


def sla_hours_for_cadence(cadence: str) -> int:
    tokens = cadence_tokens(cadence)
    if not tokens:
        return UNKNOWN_CADENCE_SLA_HOURS
    if DISABLED_AUTO_CADENCE_TOKENS.intersection(tokens):
        return DISABLED_AUTO_CADENCE_SLA_HOURS
    hours = [
        DEFAULT_CADENCE_SLA_HOURS[token]
        for token in tokens
        if token in DEFAULT_CADENCE_SLA_HOURS
    ]
    return min(hours) if hours else UNKNOWN_CADENCE_SLA_HOURS


def _interval_for_token(token: str, env: Mapping[str, str]) -> int | None:
    override = _positive_int_or_none(env.get(env_key_for_cadence(token)))
    if override is not None:
        return override
    return DEFAULT_CADENCE_INTERVAL_SECONDS.get(token)


def _positive_int_or_none(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None
