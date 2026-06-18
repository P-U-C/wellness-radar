from __future__ import annotations

from typing import Any

from fastapi import Request
from psycopg.types.json import Jsonb

from apps.api.app.security import Principal


def request_id_from(request: Request | None) -> str | None:
    if request is None:
        return None
    value = getattr(request.state, "request_id", None)
    return str(value) if value else None


def write_audit_log(
    conn: Any,
    *,
    action: str,
    actor_role: str | None = None,
    actor_id: str | None = None,
    request_id: str | None = None,
    source_name: str | None = None,
    source_run_id: int | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    source_event_id: str | None = None,
    signal_id: str | None = None,
    reject_reason: str | None = None,
    prompt_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (
          action,
          actor_role,
          actor_id,
          request_id,
          source_name,
          source_run_id,
          entity_type,
          entity_id,
          source_event_id,
          signal_id,
          reject_reason,
          prompt_version,
          metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            action,
            actor_role,
            actor_id,
            request_id,
            source_name,
            source_run_id,
            entity_type,
            entity_id,
            source_event_id,
            signal_id,
            reject_reason,
            prompt_version,
            Jsonb(metadata or {}),
        ),
    )


def audit_api_action(
    conn: Any,
    *,
    request: Request,
    principal: Principal,
    action: str,
    metadata: dict[str, Any] | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> None:
    write_audit_log(
        conn,
        action=action,
        actor_role=principal.role,
        actor_id=principal.actor_id,
        request_id=request_id_from(request),
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )
