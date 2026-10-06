from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_role
from db.models import Organization, User
from db.session import get_db
from integrations.threat_intel.service import ThreatIntelService
from jobs.runner import enqueue_job

router = APIRouter(prefix="/api/v1/threat-intel", tags=["threat-intel"])


@router.get("/status")
def get_threat_intel_status(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns feed status, last sync timestamp, and staleness of threat intelligence feeds."""
    service = ThreatIntelService(db)
    return service.get_feed_status()


def _background_refresh_threat_intel(org_id: str, job_id: str) -> dict:
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        service = ThreatIntelService(db)
        catalog = service.kev_client.fetch_catalog()
        return {"status": "refreshed", "cisa_kev_entries": len(catalog)}
    finally:
        db.close()


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
def queue_threat_intel_refresh(
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin-only background task to refresh CISA KEV and EPSS threat intelligence cache."""
    job = enqueue_job(
        task_type="threat_intel_refresh",
        fn=_background_refresh_threat_intel,
        kwargs={"org_id": current_org.id},
        org_id=current_org.id,
        db=db,
    )
    return {
        "status": "accepted",
        "job_id": job.id,
        "message": "Threat intelligence cache refresh has been queued.",
    }
