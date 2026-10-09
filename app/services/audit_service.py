from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_event(
    db: Session,
    actor_user_id: int,
    action: str,
    quote_id: int | None = None,
    quote_version_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        actor_user_id=actor_user_id,
        quote_id=quote_id,
        quote_version_id=quote_version_id,
        action=action,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event

