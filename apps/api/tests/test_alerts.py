from __future__ import annotations

from apps.api.app.services.alerts import ALERT_CONDITIONS


def test_alert_condition_catalog_covers_production_conditions() -> None:
    assert set(ALERT_CONDITIONS) == {
        "source_stale_beyond_sla",
        "adapter_failed_twice",
        "rejected_record_spike",
        "api_health_failure",
        "no_signals_window",
        "migration_failure",
        "ai_cost_threshold",
    }
