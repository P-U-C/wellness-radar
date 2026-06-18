ALTER TABLE alert_subscription
  DROP CONSTRAINT IF EXISTS alert_subscription_conditions_check;

ALTER TABLE alert_subscription
  ADD CONSTRAINT alert_subscription_conditions_check
  CHECK (
    conditions <@ ARRAY[
      'source_stale_beyond_sla',
      'adapter_run_failed',
      'adapter_failed_twice',
      'rejected_record_spike',
      'api_health_failure',
      'no_signals_window',
      'migration_failure',
      'ai_cost_threshold'
    ]::text[]
  );

CREATE INDEX IF NOT EXISTS source_run_source_success_completed_idx
  ON source_run (source_name, completed_at DESC)
  WHERE status = 'success';

CREATE INDEX IF NOT EXISTS alert_dispatch_subscription_condition_idx
  ON alert_dispatch (subscription_id, condition, dispatched_at DESC);
