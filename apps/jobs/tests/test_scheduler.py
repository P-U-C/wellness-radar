from __future__ import annotations

import asyncio

from apps.jobs.runner import RunMetrics
from apps.jobs.scheduler import SchedulerConfig, build_source_schedules, run_source_with_retry
from packages.shared.cadence import interval_seconds_for_cadence


def test_cadence_interval_mapping_and_env_overrides() -> None:
    env = {
        "WR_SCHED_HOURLY_SECONDS": "7",
        "WR_SCHED_DAILY_WEEKLY_SECONDS": "11",
    }

    assert interval_seconds_for_cadence("hourly/daily", env=env) == 7
    assert interval_seconds_for_cadence("daily/weekly", env=env) == 11
    assert interval_seconds_for_cadence("weekly", env={}) == 7 * 24 * 60 * 60
    assert interval_seconds_for_cadence("annual/as_released", env={}) == 24 * 60 * 60
    assert interval_seconds_for_cadence("manual", env={}) is None
    assert interval_seconds_for_cadence("manual/fixture", env={}) is None


def test_build_source_schedules_skips_manual_and_fixture_sources() -> None:
    rows = [
        {"source_name": "local_rss", "cadence": "hourly/daily"},
        {"source_name": "manual_seed", "cadence": "manual"},
        {"source_name": "peer_city_trends_fixture", "cadence": "manual/fixture"},
    ]

    schedules = build_source_schedules(rows, env={"WR_SCHED_HOURLY_SECONDS": "5"})

    assert [(item.source_name, item.interval_seconds) for item in schedules] == [
        ("local_rss", 5)
    ]


def test_run_source_with_retry_uses_bounded_exponential_backoff() -> None:
    calls = 0
    sleeps: list[float] = []
    alerts: list[tuple[str, str]] = []

    def runner(source_name: str, limit: int) -> RunMetrics:
        nonlocal calls
        calls += 1
        assert source_name == "local_rss"
        assert limit == 10
        if calls < 3:
            raise RuntimeError(f"boom-{calls}")
        return RunMetrics(records_fetched=1, records_persisted=1)

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    config = SchedulerConfig(
        enabled=True,
        tick_seconds=1,
        freshness_seconds=60,
        max_retries=2,
        backoff_base_seconds=1.0,
        backoff_max_seconds=1.5,
        ingest_limit=10,
        database_url="postgresql://example",
    )

    metrics = asyncio.run(
        run_source_with_retry(
            "local_rss",
            limit=10,
            config=config,
            runner=runner,
            sleep=sleep,
            alert_dispatcher=lambda source, exc: alerts.append((source, str(exc))),
        )
    )

    assert metrics == RunMetrics(records_fetched=1, records_persisted=1)
    assert calls == 3
    assert sleeps == [1.0, 1.5]
    assert alerts == [("local_rss", "boom-1"), ("local_rss", "boom-2")]
