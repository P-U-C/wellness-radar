# Production Runbook

Production is the operator-facing system. Do not deploy directly from an agent-authored PR without human approval.

## Pre-Deploy Gate

- CI is green.
- Migrations apply on a clean PostGIS database.
- RBAC tokens are configured outside the repository.
- Source rights are reviewed or explicitly blocked from public use.
- Alert subscriptions exist for all production conditions.
- People scoring correction workflow has an owner and response SLA.

## Deploy

1. Deploy the API and jobs images.
2. Apply migrations with `python -m db.migrate`.
3. Deploy the web app with the production API base URL and a production-appropriate read token strategy.
4. Start scheduled jobs.
5. Verify `/health`, `/metrics`, `/admin/observability`, source freshness, and snapshot creation.

## Operations

- Review `/admin/source-freshness` daily until scheduler reliability is proven.
- Review `/admin/audit-logs` after admin writes, adapter incidents, and correction requests.
- Keep raw payload retention to 90 days unless a source licence requires shorter retention.
- Keep public people scoring limited to public professional data with source refs.

## Rollback

Redeploy the previous application image. Keep database audit tables intact. If a migration introduced bad data, write a forward corrective migration rather than editing applied migration files.
