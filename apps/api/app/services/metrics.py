from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class RuntimeMetricsSnapshot:
    requests_total: int
    errors_total: int
    latency_ms_avg: float
    map_query_latency_ms_avg: float


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._latency_ms_sum = 0.0
        self._map_query_count = 0
        self._map_query_ms_sum = 0.0

    def observe_request(self, *, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._requests_total += 1
            self._latency_ms_sum += duration_ms
            if status_code >= 500:
                self._errors_total += 1

    def observe_map_query(self, *, duration_ms: float) -> None:
        with self._lock:
            self._map_query_count += 1
            self._map_query_ms_sum += duration_ms

    def snapshot(self) -> RuntimeMetricsSnapshot:
        with self._lock:
            return RuntimeMetricsSnapshot(
                requests_total=self._requests_total,
                errors_total=self._errors_total,
                latency_ms_avg=_avg(self._latency_ms_sum, self._requests_total),
                map_query_latency_ms_avg=_avg(
                    self._map_query_ms_sum,
                    self._map_query_count,
                ),
            )


runtime_metrics = RuntimeMetrics()


def _avg(total: float, count: int) -> float:
    return 0.0 if count == 0 else round(total / count, 3)


def prometheus_lines(
    *,
    runtime: RuntimeMetricsSnapshot,
    database_metrics: dict[str, Any],
) -> str:
    lines = [
        "# HELP wellness_api_requests_total API requests served by this process.",
        "# TYPE wellness_api_requests_total counter",
        f"wellness_api_requests_total {runtime.requests_total}",
        "# HELP wellness_api_errors_total API 5xx responses served by this process.",
        "# TYPE wellness_api_errors_total counter",
        f"wellness_api_errors_total {runtime.errors_total}",
        "# HELP wellness_api_latency_ms_avg Average API latency in milliseconds.",
        "# TYPE wellness_api_latency_ms_avg gauge",
        f"wellness_api_latency_ms_avg {runtime.latency_ms_avg}",
        "# HELP wellness_api_map_query_latency_ms_avg Average map query latency in milliseconds.",
        "# TYPE wellness_api_map_query_latency_ms_avg gauge",
        f"wellness_api_map_query_latency_ms_avg {runtime.map_query_latency_ms_avg}",
    ]
    for name, value in sorted(database_metrics.items()):
        if isinstance(value, dict):
            for label, labelled_value in sorted(value.items()):
                safe_label = str(label).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{name}{{label="{safe_label}"}} {labelled_value}')
        else:
            lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"
