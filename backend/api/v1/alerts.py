from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_role
from core.errors import ResourceNotFoundError
from db.models import AlertDelivery, Organization, RiskAlert, User
from db.session import get_db
from services.alerts.alert_service import AlertService
from services.audit import AuditService

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    dataset_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Lists persistent risk alerts scoped to the organization."""
    filters = [RiskAlert.organization_id == current_org.id]
    if status:
        filters.append(RiskAlert.status == status)
    if severity:
        filters.append(RiskAlert.severity == severity)
    if owner_id:
        filters.append(RiskAlert.owner_id == owner_id)
    if dataset_id:
        filters.append(RiskAlert.dataset_id == dataset_id)

    query = select(RiskAlert).where(*filters)
    total = db.query(RiskAlert).filter(*filters).count()
    offset = (page - 1) * page_size
    alerts = db.scalars(query.order_by(RiskAlert.created_at.desc()).offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "alerts": [
            {
                "id": a.id,
                "severity": a.severity,
                "category": a.category,
                "title": a.title,
                "description": a.description,
                "status": a.status,
                "owner_id": a.owner_id,
                "opened_at": a.opened_at.isoformat(),
                "due_at": a.due_at.isoformat() if a.due_at else None,
                "closed_at": a.closed_at.isoformat() if a.closed_at else None,
            }
            for a in alerts
        ],
    }


@router.get("/{alert_id}")
def get_alert_detail(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns details, evidence refs, and delivery history for an alert."""
    alert = db.scalars(
        select(RiskAlert).where(
            RiskAlert.id == alert_id,
            RiskAlert.organization_id == current_org.id,
        )
    ).first()

    if not alert:
        raise ResourceNotFoundError(message="Alert not found")

    deliveries = db.scalars(
        select(AlertDelivery).where(AlertDelivery.alert_id == alert.id)
    ).all()

    return {
        "id": alert.id,
        "severity": alert.severity,
        "category": alert.category,
        "title": alert.title,
        "description": alert.description,
        "evidence_refs": alert.evidence_refs,
        "status": alert.status,
        "owner_id": alert.owner_id,
        "opened_at": alert.opened_at.isoformat(),
        "due_at": alert.due_at.isoformat() if alert.due_at else None,
        "closed_at": alert.closed_at.isoformat() if alert.closed_at else None,
        "deliveries": [
            {
                "id": d.id,
                "channel": d.channel,
                "recipient": d.recipient,
                "state": d.state,
                "attempts": d.attempts,
                "provider_ref": d.provider_ref,
                "sanitized_error": d.sanitized_error,
                "sent_at": d.sent_at.isoformat() if d.sent_at else None,
            }
            for d in deliveries
        ],
    }


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Transitions alert status to 'acknowledged'."""
    service = AlertService(db)
    alert = service.transition_status(
        alert_id, "acknowledged", actor_id=current_user.id, org_id=current_org.id
    )
    AuditService.log(
        db=db,
        org_id=current_org.id,
        actor_id=current_user.id,
        action="alert.acknowledged",
        resource_type="alert",
        resource_id=alert_id,
    )
    return {"status": "success", "alert_id": alert.id, "new_status": alert.status}


class AssignRequest(BaseModel):
    owner_id: str


@router.post("/{alert_id}/assign")
def assign_alert(
    alert_id: str,
    payload: AssignRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Assigns an alert owner and moves status to 'in_progress'."""
    from db.models import Membership

    member = db.scalars(
        select(Membership).where(
            Membership.organization_id == current_org.id,
            Membership.user_id == payload.owner_id,
        )
    ).first()
    if not member:
        raise ResourceNotFoundError(message="Assignee is not a member of this organization")

    service = AlertService(db)
    service.assign_owner(alert_id, payload.owner_id, org_id=current_org.id)
    alert = service.transition_status(
        alert_id, "in_progress", actor_id=current_user.id, org_id=current_org.id
    )
    return {"status": "success", "alert_id": alert.id, "owner_id": payload.owner_id, "new_status": alert.status}


@router.post("/{alert_id}/escalate")
def escalate_alert(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Escalates alert severity to critical and triggers immediate notification."""
    alert = db.scalars(
        select(RiskAlert).where(
            RiskAlert.id == alert_id,
            RiskAlert.organization_id == current_org.id,
        )
    ).first()
    if not alert:
        raise ResourceNotFoundError(message="Alert not found")

    alert.severity = "critical"
    alert.status = "open"
    db.commit()

    service = AlertService(db)
    service.delivery_service.dispatch_alert(alert)
    return {"status": "success", "alert_id": alert.id, "severity": alert.severity}


@router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Marks an alert as resolved."""
    service = AlertService(db)
    alert = service.transition_status(
        alert_id, "resolved", actor_id=current_user.id, org_id=current_org.id
    )
    return {"status": "success", "alert_id": alert.id, "new_status": alert.status}


@router.post("/{alert_id}/close")
def close_alert(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Marks an alert as closed."""
    service = AlertService(db)
    alert = service.transition_status(
        alert_id, "closed", actor_id=current_user.id, org_id=current_org.id
    )
    return {"status": "success", "alert_id": alert.id, "new_status": alert.status}


@router.get("/{alert_id}/deliveries")
def get_alert_deliveries(
    alert_id: str,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns channel delivery attempts, simulated vs sent status, and errors."""
    alert = db.scalars(
        select(RiskAlert).where(
            RiskAlert.id == alert_id,
            RiskAlert.organization_id == current_org.id,
        )
    ).first()
    if not alert:
        raise ResourceNotFoundError(message="Alert not found")

    deliveries = db.scalars(
        select(AlertDelivery).where(AlertDelivery.alert_id == alert.id)
    ).all()

    return [
        {
            "id": d.id,
            "channel": d.channel,
            "recipient": d.recipient,
            "state": d.state,
            "attempts": d.attempts,
            "provider_ref": d.provider_ref,
            "sanitized_error": d.sanitized_error,
            "sent_at": d.sent_at.isoformat() if d.sent_at else None,
            "created_at": d.created_at.isoformat(),
        }
        for d in deliveries
    ]
