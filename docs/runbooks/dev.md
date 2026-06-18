# Dev Runbook

The dev environment is for shared agent and developer validation before staging.

## Deploy

1. Build API/jobs/web images from the PR branch.
2. Apply migrations with `python -m db.migrate`.
3. Run the M2 and M3 jobs with recorded-fixture tests already passing in CI.
4. Configure RBAC tokens through the deployment secret manager.
5. Point the web app at the dev API with `VITE_API_BASE_URL`.

## Checks

- `GET /health` returns `{"status":"ok"}`.
- `GET /metrics` returns Prometheus text.
- Protected admin endpoints return `401` without a token and succeed with an analyst/admin token.
- Kiosk mode renders at `/?mode=kiosk`.
- No adapter uses live network in tests.

## Rollback

Redeploy the previous image set and do not roll back migrations unless a migration is explicitly documented as reversible. Preserve `audit_log`, `rejected_record`, and `source_run` rows for incident review.
