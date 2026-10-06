from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org
from core.errors import ResourceNotFoundError
from db.models import IngestionJob, Organization
from db.session import get_db

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns background job execution progress and safe summary."""
    job = db.scalars(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.organization_id == current_org.id,
        )
    ).first()

    if not job:
        raise ResourceNotFoundError(message="Job not found")

    return {
        "job_id": job.id,
        "task_type": job.task_type,
        "state": job.state,
        "progress_pct": job.progress_pct,
        "result_summary": job.result_summary,
        "safe_error_code": job.safe_error_code,
        "safe_error_message": job.safe_error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat(),
    }
