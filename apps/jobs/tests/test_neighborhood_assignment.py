from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.jobs.analytics.neighborhoods import (
    SOURCE_NAME,
    NeighborhoodBoundary,
    run_neighborhood_assignment,
)
from packages.geo.bc_gate import CanonicalGeoRecord, GeoGateResult


def test_neighborhood_assignment_persists_boundaries_and_runs_backfill() -> None:
    repository = InMemoryNeighborhoodRepository()

    metrics = run_neighborhood_assignment(repository, client=FakeBoundaryClient())

    assert metrics.records_fetched == 1
    assert metrics.records_rejected == 0
    assert metrics.records_persisted == 7
    assert repository.boundaries[0].neighborhood == "Mount Pleasant"
    assert repository.boundaries[0].source_refs[0]["source_name"] == SOURCE_NAME
    assert repository.source_runs[1]["status"] == "success"


class FakeBoundaryClient:
    def get_json(self, url: str) -> dict[str, Any]:
        return {
            "results": [
                {
                    "name": "Mount Pleasant",
                    "geom": {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-123.11, 49.26],
                                    [-123.09, 49.26],
                                    [-123.09, 49.28],
                                    [-123.11, 49.28],
                                    [-123.11, 49.26],
                                ]
                            ],
                        },
                        "properties": {},
                    },
                    "geo_point_2d": {"lat": 49.27, "lon": -123.10},
                }
            ]
        }


@dataclass
class InMemoryNeighborhoodRepository:
    boundaries: list[NeighborhoodBoundary] = field(default_factory=list)
    raw_payloads: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected: list[tuple[CanonicalGeoRecord, GeoGateResult, str]] = field(default_factory=list)
    source_runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    _run_id: int = 0

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any:
        raise RuntimeError("in-memory neighborhood repository has no boundary table")

    def ensure_source_rights(self, source_name: str) -> None:
        if source_name != SOURCE_NAME:
            raise RuntimeError(f"source_registry row missing for {source_name}")

    def create_source_run(self, source_name: str) -> int:
        self._run_id += 1
        self.source_runs[self._run_id] = {"source_name": source_name, "status": "partial"}
        return self._run_id

    def complete_source_run(
        self,
        run_id: int,
        *,
        status: str,
        records_fetched: int,
        records_persisted: int,
        records_rejected: int,
        error_count: int,
        error_message: str | None = None,
    ) -> None:
        self.source_runs[run_id] = {
            **self.source_runs[run_id],
            "status": status,
            "records_fetched": records_fetched,
            "records_persisted": records_persisted,
            "records_rejected": records_rejected,
            "error_count": error_count,
            "error_message": error_message,
        }

    def upsert_raw_payload(
        self, source_name: str, source_record_id: str, raw: dict[str, Any]
    ) -> str:
        raw_payload_id = f"raw_{source_name}_{source_record_id}"
        self.raw_payloads[raw_payload_id] = raw
        return raw_payload_id

    def write_rejection(
        self,
        record: CanonicalGeoRecord,
        result: GeoGateResult,
        raw_payload_id: str,
    ) -> None:
        self.rejected.append((record, result, raw_payload_id))

    def upsert_boundary(self, boundary: NeighborhoodBoundary, gate: GeoGateResult) -> None:
        assert gate.passes
        self.boundaries.append(boundary)

    def mark_native_neighborhoods(self) -> int:
        return 2

    def assign_point_in_polygon_neighborhoods(self) -> int:
        return 3

    def assign_nearest_centroid_neighborhoods(self) -> int:
        return 1

    def close(self) -> None:
        return None
