from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_role
from db.models import Organization, User
from db.session import get_db
from services.alerts.remediation_service import RemediationService

router = APIRouter(prefix="/api/v1/remediation-tasks", tags=["remediation"])


class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # critical, high, medium, low
    due_date: Optional[datetime] = None
    alert_id: Optional[str] = None
    finding_id: Optional[str] = None
    control_id: Optional[str] = None
    asset_id: Optional[str] = None
    owner_id: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    status: Optional[str] = None  # todo, in_progress, review, completed, cancelled
    action_notes: Optional[str] = None
    verification_evidence: Optional[str] = None
    owner_id: Optional[str] = None


@router.get("")
def list_remediation_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Lists remediation tasks scoped by organization."""
    service = RemediationService(db)
    tasks = service.list_tasks(current_org.id, status=status, priority=priority)
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "owner_id": t.owner_id,
            "action_notes": t.action_notes,
            "verification_evidence": t.verification_evidence,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.post("")
def create_remediation_task(
    payload: CreateTaskRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Creates a new owned remediation task with due date SLA tracking."""
    service = RemediationService(db)
    task = service.create_task(
        org_id=current_org.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        alert_id=payload.alert_id,
        finding_id=payload.finding_id,
        control_id=payload.control_id,
        asset_id=payload.asset_id,
        owner_id=payload.owner_id or current_user.id,
    )
    return {
        "status": "created",
        "task_id": task.id,
        "title": task.title,
        "due_date": task.due_date.isoformat() if task.due_date else None,
    }


@router.patch("/{task_id}")
def update_remediation_task(
    task_id: str,
    payload: UpdateTaskRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Updates remediation status, action notes, and completion verification evidence."""
    service = RemediationService(db)
    task = service.update_task(
        task_id=task_id,
        org_id=current_org.id,
        status=payload.status,
        action_notes=payload.action_notes,
        verification_evidence=payload.verification_evidence,
        owner_id=payload.owner_id,
    )
    return {
        "status": "updated",
        "task_id": task.id,
        "new_status": task.status,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
