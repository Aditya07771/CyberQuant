from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_dataset_access, require_role
from core.errors import ResourceNotFoundError
from db.models import Dataset, Organization, RegulatoryAssessment, RegulatoryRule, User
from db.session import get_db
from risk_engine.regulatory.engine import RegulatoryAssessmentEngine
from services.audit import AuditService

router = APIRouter(prefix="/api/v1", tags=["regulatory"])


@router.get("/regulatory/rules")
def list_regulatory_rules(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Lists applicable versioned Indian and global cybersecurity regulatory rules."""
    engine = RegulatoryAssessmentEngine(db)
    engine.sync_rules()

    rules = db.scalars(select(RegulatoryRule).order_by(RegulatoryRule.framework_name)).all()
    return [
        {
            "id": r.id,
            "framework_name": r.framework_name,
            "instrument_id": r.instrument_id,
            "provision_citation": r.provision_citation,
            "title": r.title,
            "description": r.description,
            "statutory_penalty_max_usd": r.statutory_penalty_max_usd,
            "statutory_currency": r.statutory_currency,
            "effective_from": r.effective_from.isoformat(),
            "source_url": r.source_url,
            "verified_date": r.verified_date.isoformat(),
            "reviewer_status": r.reviewer_status,
        }
        for r in rules
    ]


@router.post("/datasets/{dataset_id}/regulatory/assessments")
def evaluate_regulatory_exposure(
    dataset_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    current_org: Organization = Depends(get_current_org),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Triggers evidence-based regulatory exposure evaluation for the dataset."""
    engine = RegulatoryAssessmentEngine(db)
    assessments = engine.evaluate_dataset(dataset.id, dataset.active_version_id)
    return {
        "status": "success",
        "dataset_id": dataset.id,
        "total_assessments": len(assessments),
    }


class AssessmentReviewRequest(BaseModel):
    decision: str  # reviewed, not_applicable, accepted_risk
    rationale: str
    evidence_refs: Optional[list] = None


@router.post("/regulatory/assessments/{assessment_id}/review")
def review_regulatory_assessment(
    assessment_id: str,
    payload: AssessmentReviewRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Compliance/legal reviewer records a formal review decision and audit trail."""
    from db.models import Dataset

    assessment = db.scalars(
        select(RegulatoryAssessment)
        .join(Dataset, RegulatoryAssessment.dataset_id == Dataset.id)
        .where(
            RegulatoryAssessment.id == assessment_id,
            Dataset.organization_id == current_org.id,
        )
    ).first()

    if not assessment:
        raise ResourceNotFoundError(message="Assessment not found")

    now = datetime.now(timezone.utc)
    assessment.status = payload.decision
    assessment.rationale = payload.rationale
    if payload.evidence_refs:
        assessment.evidence_refs = payload.evidence_refs
    assessment.reviewer_id = current_user.id
    assessment.reviewed_at = now

    AuditService.log(
        db=db,
        org_id=current_org.id,
        actor_id=current_user.id,
        action="regulatory.assessment_reviewed",
        resource_type="regulatory_assessment",
        resource_id=assessment.id,
        details={"decision": payload.decision, "rationale": payload.rationale},
    )

    db.commit()
    db.refresh(assessment)
    return {"status": "success", "assessment_id": assessment.id, "new_status": assessment.status}
