from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from db.models import AuditEvent


class AuditService:
    @staticmethod
    def log(
        db: Session,
        org_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Appends an immutable audit event."""
        event = AuditEvent(
            organization_id=org_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(event)
        db.commit()
        return event
