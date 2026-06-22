from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from apps.api.app.config import settings
from apps.api.app.services.alerts import (
    AlertEvaluation,
    dispatch_alert_evaluations,
    evaluate_alert_conditions,
)
from apps.api.app.services.audit import write_audit_log
from apps.jobs.importers.people_csv import import_people_csv
from apps.jobs.runner import (
    DatabaseRepository,
    RunMetrics,
    adapter_for_name,
    run_adapter,
    run_event_adapter,
    run_orgbook_enrichment,
)
from packages.shared.cadence import interval_seconds_for_cadence

logger = logging.getLogger("wellness_radar.jobs.scheduler")

Runner = Callable[[str, int], RunMetrics]
Sleep = Callable[[float], Awaitable[None]]
AlertDispatcher = Callable[[str, BaseException], None]

EVENT_ADAPTER_SOURCES = {"local_rss", "bc_gov_news_rss", "health_canada_recalls"}


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    tick_seconds: int
    freshness_seconds: int
    max_retries: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    ingest_limit: int
    database_url: str

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        database_url: str | None = None,
    ) -> SchedulerConfig:
        values = env or os.environ
        return cls(
            enabled=_env_bool(values, "WR_SCHED_ENABLED", default=True),
            tick_seconds=_env_int(values, "WR_SCHED_TICK_SECONDS", default=60),
            freshness_seconds=_env_int(values, "WR_SCHED_FRESHNESS_SECONDS", default=300),
            max_retries=_env_int(values, "WR_SCHED_MAX_RETRIES", default=2),
            backoff_base_seconds=_env_float(
                values,
                "WR_SCHED_BACKOFF_BASE_SECONDS",
                default=60.0,
            ),
            backoff_max_seconds=_env_float(
                values,
                "WR_SCHED_BACKOFF_MAX_SECONDS",
                default=3600.0,
            ),
            ingest_limit=_env_int(
                values,
                "WR_SCHED_INGEST_LIMIT",
                default=_env_int(values, "M2_INGEST_LIMIT", default=75),
            ),
            database_url=database_url or settings.database_url,
        )


@dataclass(frozen=True)
class SourceSchedule:
    source_name: str
    cadence: str
    interval_seconds: int


@dataclass
class SourceRuntime:
    schedule: SourceSchedule
    next_run_monotonic: float
    running: bool = False


def load_source_schedules(
    *,
    database_url: str | None = None,
    env: Mapping[str, str] | None = None,
) -> list[SourceSchedule]:
    with psycopg.connect(database_url or settings.database_url, row_factory=dict_row) as conn:
        rows = conn.execute(
            """
            SELECT source_name, cadence
            FROM source_registry
            WHERE enabled = TRUE
            ORDER BY source_name
            """
        ).fetchall()
    return build_source_schedules(rows, env=env)


def build_source_schedules(
    rows: list[dict[str, Any]],
    *,
    env: Mapping[str, str] | None = None,
) -> list[SourceSchedule]:
    schedules: list[SourceSchedule] = []
    for row in rows:
        cadence = str(row["cadence"])
        interval = interval_seconds_for_cadence(cadence, env=env)
        if interval is None:
            logger.info(
                "source %s with cadence %s is disabled for automatic scheduling",
                row["source_name"],
                cadence,
            )
            continue
        schedules.append(
            SourceSchedule(
                source_name=str(row["source_name"]),
                cadence=cadence,
                interval_seconds=interval,
            )
        )
    return schedules


def run_registered_source(source_name: str, limit: int) -> RunMetrics:
    if source_name in EVENT_ADAPTER_SOURCES:
        return run_event_adapter(adapter_for_name(source_name, limit))
    if source_name == "orgbook_bc":
        return run_orgbook_enrichment(limit=limit)
    if source_name == "manual_people_csv":
        return _coerce_run_metrics(import_people_csv(DatabaseRepository(), path=None))
    if source_name == "statcan_wds":
        from apps.jobs.analytics.denominators import run_statcan_denominators

        return run_statcan_denominators()
    if source_name == "peer_city_trends_fixture":
        from apps.jobs.analytics.trends import run_peer_city_trends

        return run_peer_city_trends()
    if source_name == "manual_seed":
        return run_adapter(adapter_for_name(source_name, limit))
    return run_adapter(adapter_for_name(source_name, limit))


def _coerce_run_metrics(metrics: Any) -> RunMetrics:
    return RunMetrics(
        records_fetched=metrics.records_fetched,
        records_persisted=metrics.records_persisted,
        records_rejected=metrics.records_rejected,
        error_count=metrics.error_count,
        error_message=metrics.error_message,
    )


async def run_source_with_retry(
    source_name: str,
    *,
    limit: int,
    config: SchedulerConfig,
    runner: Runner = run_registered_source,
    sleep: Sleep = asyncio.sleep,
    alert_dispatcher: AlertDispatcher | None = None,
) -> RunMetrics | None:
    attempts = 0
    while True:
        try:
            metrics = await asyncio.to_thread(runner, source_name, limit)
            if attempts:
                logger.info("source %s succeeded after %s retry attempt(s)", source_name, attempts)
            return metrics
        except Exception as exc:
            attempts += 1
            logger.exception("source %s scheduled run failed on attempt %s", source_name, attempts)
            dispatcher = alert_dispatcher or dispatch_adapter_failure_alert
            dispatcher(source_name, exc)
            if attempts > config.max_retries:
                logger.error(
                    "source %s exhausted %s retry attempt(s)",
                    source_name,
                    config.max_retries,
                )
                return None
            delay = min(
                config.backoff_max_seconds,
                config.backoff_base_seconds * (2 ** (attempts - 1)),
            )
            await sleep(delay)


def dispatch_adapter_failure_alert(
    source_name: str,
    exc: BaseException,
    *,
    database_url: str | None = None,
) -> None:
    evaluation = AlertEvaluation(
        condition="adapter_run_failed",
        firing=True,
        severity="critical",
        summary=f"{source_name} adapter run failed",
        details={"source_name": source_name, "error_message": str(exc)},
    )
    with psycopg.connect(database_url or settings.database_url, row_factory=dict_row) as conn:
        result = dispatch_alert_evaluations(conn, [evaluation])
        write_audit_log(
            conn,
            action="scheduler_adapter_failure_alert",
            actor_role="system",
            actor_id="jobs-scheduler",
            source_name=source_name,
            metadata={**result, "error_message": str(exc)},
        )


def dispatch_stale_source_alerts(*, database_url: str | None = None) -> dict[str, int]:
    with psycopg.connect(database_url or settings.database_url, row_factory=dict_row) as conn:
        evaluations = [
            item
            for item in evaluate_alert_conditions(conn)
            if item.firing and item.condition == "source_stale_beyond_sla"
        ]
        result = dispatch_alert_evaluations(conn, evaluations)
        write_audit_log(
            conn,
            action="scheduler_freshness_evaluated",
            actor_role="system",
            actor_id="jobs-scheduler",
            metadata={
                **result,
                "stale_count": len(evaluations),
                "source_names": [item.details.get("source_name") for item in evaluations],
            },
        )
        return result


async def run_scheduler_forever(config: SchedulerConfig | None = None) -> None:
    active_config = config or SchedulerConfig.from_env()
    if not active_config.enabled:
        logger.info("scheduler disabled by WR_SCHED_ENABLED=false")
        await _sleep_forever()

    schedules = load_source_schedules(
        database_url=active_config.database_url,
        env=os.environ,
    )
    now = time.monotonic()
    runtimes = [
        SourceRuntime(schedule=schedule, next_run_monotonic=now + schedule.interval_seconds)
        for schedule in schedules
    ]
    logger.info("registered %s recurring source job(s)", len(runtimes))
    next_freshness_monotonic = now + active_config.freshness_seconds
    stop_event = asyncio.Event()
    _install_stop_handlers(stop_event)

    while not stop_event.is_set():
        loop_now = time.monotonic()
        due = [
            runtime
            for runtime in runtimes
            if not runtime.running and runtime.next_run_monotonic <= loop_now
        ]
        for runtime in due:
            runtime.running = True
            asyncio.create_task(_run_due_source(runtime, active_config))

        if loop_now >= next_freshness_monotonic:
            await asyncio.to_thread(
                dispatch_stale_source_alerts,
                database_url=active_config.database_url,
            )
            next_freshness_monotonic = loop_now + active_config.freshness_seconds

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=active_config.tick_seconds,
            )


async def _run_due_source(runtime: SourceRuntime, config: SchedulerConfig) -> None:
    schedule = runtime.schedule
    try:
        await run_source_with_retry(
            schedule.source_name,
            limit=config.ingest_limit,
            config=config,
            alert_dispatcher=lambda source, exc: dispatch_adapter_failure_alert(
                source,
                exc,
                database_url=config.database_url,
            ),
        )
    finally:
        runtime.next_run_monotonic = time.monotonic() + schedule.interval_seconds
        runtime.running = False


async def _sleep_forever() -> None:
    while True:
        await asyncio.sleep(3600)


def _install_stop_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)


def _env_bool(values: Mapping[str, str], key: str, *, default: bool) -> bool:
    value = values.get(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(values: Mapping[str, str], key: str, *, default: int) -> int:
    value = values.get(key)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_float(values: Mapping[str, str], key: str, *, default: float) -> float:
    value = values.get(key)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_scheduler_forever())


if __name__ == "__main__":
    main()
