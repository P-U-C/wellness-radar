# Staging Runbook

Staging is the pre-production environment with scheduled jobs and production-like RBAC.

## Deploy

1. Merge only through a reviewed PR.
2. Confirm CI passed web lint/typecheck/test, Python lint/typecheck/test, geo tests, adapter fixture tests, and migration check.
3. Apply migrations with `python -m db.migrate`.
4. Run a bounded M2 ingestion and M3 analytics refresh.
5. Create at least one alert subscription for stale source and adapter failure conditions.
6. Verify `/admin/observability` with an analyst token.

## Smoke Tests

```bash
curl -s "$API_BASE/health"
curl -s "$API_BASE/metrics"
curl -s -H "Authorization: Bearer $ANALYST_TOKEN" "$API_BASE/admin/source-freshness"
curl -s -H "Authorization: Bearer $ANALYST_TOKEN" "$API_BASE/admin/alerts/evaluate"
```

## Release Readiness

- Source-rights rows are reviewed or explicitly marked as needing human review.
- People scoring correction requests can be created and audited.
- Export snapshots can be created with an admin token.
