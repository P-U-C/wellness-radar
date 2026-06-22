# Scheduler Notes

Date: 2026-06-18 UTC

## What Was Built

- `apps/jobs/scheduler.py` now runs a real asyncio scheduler instead of idling forever.
- On startup it reads enabled `source_registry` rows, derives an interval from each cadence, and registers recurring per-source jobs for auto-runnable sources.
- Scheduled jobs call the existing runner entrypoints (`run_adapter`, `run_event_adapter`, `run_orgbook_enrichment`, `run_statcan_denominators`, and `run_peer_city_trends`) so ingestion semantics, upserts, `source_run`, and audit behavior stay aligned with the startup path.
- Per-source failures are isolated. A source run failure is retried with bounded exponential backoff and does not stop the scheduler or other source jobs.
- Failed scheduled attempts dispatch an `adapter_run_failed` alert and write scheduler audit metadata.
- A periodic freshness tick evaluates stale enabled sources using the last successful `source_run`, not the latest failed/partial run.
- Alert dispatch now uses a provider interface:
  - default provider writes auditable `alert_dispatch` rows locally;
  - webhook provider posts JSON to `WR_ALERT_WEBHOOK_URL` and writes `alert_dispatch` rows with `delivered` or `failed`;
  - `/admin/alerts/dispatch-stub` still works and records `stubbed`;
  - `/admin/alerts/dispatch` uses the configured provider.

## Cadence Mapping

Automatic scheduling is disabled when cadence contains `manual` or `fixture`.

| Cadence token | Default interval |
| --- | ---: |
| `15_min` | 900 seconds |
| `hourly` | 3,600 seconds |
| `daily` | 86,400 seconds |
| `weekdays` | 86,400 seconds |
| `weekly` | 604,800 seconds |
| `annual` | 31,536,000 seconds |
| `as_published` | 86,400 seconds |
| `as_released` | 86,400 seconds |

Composite cadences use the shortest enabled token interval. Examples:

- `hourly/daily` -> hourly
- `daily/weekly` -> daily
- `annual/as_released` -> daily poll
- `manual` and `manual/fixture` -> not auto-scheduled

Exact composite overrides are supported first, for example `WR_SCHED_DAILY_WEEKLY_SECONDS`.
Token overrides are supported next, for example `WR_SCHED_DAILY_SECONDS`.

## Env Vars

- `WR_SCHED_ENABLED=true`
- `WR_SCHED_TICK_SECONDS=60`
- `WR_SCHED_FRESHNESS_SECONDS=300`
- `WR_SCHED_INGEST_LIMIT=75`
- `WR_SCHED_MAX_RETRIES=2`
- `WR_SCHED_BACKOFF_BASE_SECONDS=60`
- `WR_SCHED_BACKOFF_MAX_SECONDS=3600`
- `WR_SCHED_HOURLY_SECONDS=3600`
- `WR_SCHED_DAILY_SECONDS=86400`
- `WR_SCHED_WEEKLY_SECONDS=604800`
- `WR_SCHED_ANNUAL_SECONDS=31536000`
- `WR_SCHED_AS_PUBLISHED_SECONDS=86400`
- `WR_SCHED_AS_RELEASED_SECONDS=86400`
- `WR_ALERT_WEBHOOK_URL=`

## Run / Verify

Local default:

```bash
python3 -m db.migrate
python3 -m apps.jobs.runner m2 --limit ${M2_INGEST_LIMIT:-75}
python3 -m apps.jobs.runner m3
python3 -m apps.jobs.scheduler
```

Compose still runs M2/M3 once before starting the scheduler, so the first recurring run happens after each source interval instead of immediately double-ingesting.

Webhook delivery:

```bash
WR_ALERT_WEBHOOK_URL=https://example.test/wellness-radar-alerts python3 -m apps.jobs.scheduler
```

The webhook receives JSON with `condition`, `severity`, `summary`, `details`, `subscription_id`, `channel`, `target`, `provider`, and `fired_at`. Every attempt is recorded in `alert_dispatch`.

Admin dispatch:

```bash
curl -X POST http://127.0.0.1:8000/admin/alerts/dispatch \
  -H "X-API-Key: $API_ADMIN_TOKEN"
```

Back-compat stub:

```bash
curl -X POST http://127.0.0.1:8000/admin/alerts/dispatch-stub \
  -H "X-API-Key: $API_ADMIN_TOKEN"
```

## Verification Results

```bash
python3 -m pytest
# 50 passed

python3 -m ruff check .
# passed

python3 -m mypy apps packages db
# passed, 68 source files
```

Clean migration verification used a disposable PostGIS container on port `55432`.
Applied migrations:

- `001_canonical_schema.sql`
- `002_source_registry_seed.sql`
- `003_m2_private_alpha.sql`
- `004_m3_intelligence_beta.sql`
- `005_m4_production_hardening.sql`
- `006_scheduler_alert_delivery.sql`

## Honest Gaps

- There is no distributed lock yet. Run only one jobs scheduler replica unless a DB advisory-lock layer is added.
- Alert dispatch is intentionally subscription-driven; if no enabled `alert_subscription` matches a firing condition, no `alert_dispatch` row is created.
- The scheduler keeps the existing startup M2/M3 run in Compose. That avoids waiting a full interval after container start, but it means startup ingestion and recurring ingestion are still separate phases.
