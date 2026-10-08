from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import ResourceNotFoundError
from db.models import RemediationTask


class RemediationService:
    def __init__(self, db: Session):
        self.db = db

    def list_tasks(
        self,
        org_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[RemediationTask]:
        """Lists remediation tasks scoped by organization."""
        query = select(RemediationTask).where(RemediationTask.organization_id == org_id)
        if status:
            query = query.where(RemediationTask.status == status)
        if priority:
            query = query.where(RemediationTask.priority == priority)
        return list(self.db.scalars(query.order_by(RemediationTask.created_at.desc())).all())

    def create_task(
        self,
        org_id: str,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[datetime] = None,
        alert_id: Optional[str] = None,
        finding_id: Optional[str] = None,
        control_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> RemediationTask:
        """Creates a new tracked remediation task."""
        now = datetime.now(timezone.utc)
        task = RemediationTask(
            organization_id=org_id,
            alert_id=alert_id,
            finding_id=finding_id,
            control_id=control_id,
            asset_id=asset_id,
            title=title,
            description=description,
            owner_id=owner_id,
            priority=priority,
            due_date=due_date,
            status="todo",
            created_at=now,
            updated_at=now,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_task(
        self,
        task_id: str,
        org_id: str,
        status: Optional[str] = None,
        action_notes: Optional[str] = None,
        verification_evidence: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> RemediationTask:
        """Updates remediation progress, verification evidence, or status."""
        task = self.db.scalars(
            select(RemediationTask).where(
                RemediationTask.id == task_id,
                RemediationTask.organization_id == org_id,
            )
        ).first()

        if not task:
            raise ResourceNotFoundError(message="Remediation task not found")

        now = datetime.now(timezone.utc)
        if status:
            task.status = status
            if status == "completed":
                task.completed_at = now
        if action_notes is not None:
            task.action_notes = action_notes
        if verification_evidence is not None:
            task.verification_evidence = verification_evidence
        if owner_id is not None:
            task.owner_id = owner_id

        task.updated_at = now
        self.db.commit()
        self.db.refresh(task)
        return task
