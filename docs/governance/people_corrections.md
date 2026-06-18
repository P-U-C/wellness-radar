# People Scoring Correction Workflow

Public people scoring remains limited to public professional records.

## Intake

Correction requests are accepted through:

```text
POST /people/{person_id}/correction-requests
```

The endpoint is RBAC-gated in the private build and writes to `people_correction_request`. Each request is audited with `people_correction_requested`.

## Review

1. Confirm the person record uses only public professional data.
2. Verify the submitted correction source.
3. Update the source data or mark the request rejected.
4. Re-run influence scoring.
5. Keep the audit log and correction request status for review.

## Public Launch Requirement

Before public launch, assign a human owner and response SLA for open correction requests. Do not publish people scoring without this ownership.
