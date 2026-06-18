# Incident Playbooks

## Source Stale Beyond SLA

1. Check `/admin/source-freshness`.
2. Inspect the latest `source_run.error_message`.
3. Re-run the adapter with a bounded limit in staging first if the failure mode is unclear.
4. Record the action in the incident notes and preserve audit rows.

## Adapter Failed Twice

1. Review the latest two `source_run` rows and related `audit_log` rows.
2. Confirm whether the source changed shape, terms, rate limits, or auth.
3. Disable the source only if continuing would violate rights, cost, or data-quality constraints.
4. Add or update a fixture test before re-enabling.

## Rejected-Record Spike

1. Inspect `/admin/rejected-records`.
2. Separate expected BC-gate rejections from WA contamination.
3. Add a fixture for any new contamination pattern.
4. Do not weaken `bc_gate` to recover volume.

## API Health Failure

1. Check container status and database connectivity.
2. Verify migrations are applied.
3. Inspect structured JSON logs by `request_id`.
4. Roll back the application image if the failure is code-related.

## No Signals Window

1. Check whether sources ran successfully.
2. Confirm source freshness and adapter persisted counts.
3. Review category/source filters before treating it as a data outage.

## Migration Failure

1. Stop deploy promotion.
2. Capture the migration error and database version.
3. Fix with a new forward migration.
4. Re-run clean PostGIS migration verification.

## AI Cost Threshold

1. Confirm whether the live AI provider is enabled.
2. Check enriched signal counts and prompt version.
3. Disable AI enrichment if cost exceeds the approved threshold.
4. Keep deterministic signal generation active.
