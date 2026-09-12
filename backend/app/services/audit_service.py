"""
Real, persistent audit logging.

Previously the AuditLog table existed and GET /api/audit read from it, but
nothing anywhere ever wrote a row into it - the audit log page was silently
empty forever. log_action() is the one place every endpoint below calls to
record an action; it never receives passwords, tokens, or API keys, and
`details` must stay limited to non-secret metadata.
"""

import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.domain import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    user: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    try:
        entry = AuditLog(
            user=user or "anonymous",
            action=action,
            resource=resource_type,  # legacy column, kept in sync for old readers
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            result=result,
            details=json.dumps(details, default=str) if details else None,
            correlation_id=correlation_id or uuid4().hex[:12],
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        # Audit logging must never break the actual request it's describing.
        db.rollback()
        logger.error(f"[AUDIT] Failed to record action={action} user={user}: {e}")
