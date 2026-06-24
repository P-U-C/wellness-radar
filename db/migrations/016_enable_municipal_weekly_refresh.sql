-- Enable weekly auto-refresh for the aggregate municipal facilities adapter.
--
-- Background: West Vancouver / Vancouver / Surrey / Burnaby municipal facility
-- data is already ingested by the one-time M2 startup run (the in-code
-- MunicipalSource rows are enabled=True). However the source_registry row for
-- the aggregate adapter was seeded enabled=FALSE in 002, which only the
-- recurring scheduler reads (apps/jobs/scheduler.py load_source_schedules:
-- WHERE enabled = TRUE). The net effect was that municipal data never refreshed
-- after deploy and showed as stale in freshness metrics.
--
-- This flips ONLY the aggregate `municipal_facilities` row to enabled=TRUE.
-- The aggregate MunicipalFacilitiesAdapter internally skips the per-municipality
-- `needs_review` sources (Richmond, North Vancouver) that have no fetch path,
-- so no failing fetch is scheduled. The per-municipality registry rows
-- (municipal_facilities_*) stay disabled because they do not resolve to their
-- own adapters. Cadence is already 'weekly' from migration 002.

UPDATE source_registry
SET enabled = TRUE
WHERE source_name = 'municipal_facilities';
