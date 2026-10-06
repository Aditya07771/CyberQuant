from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_role
from db.models import Organization, RiskPolicy, User
from db.session import get_db

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


class RiskPolicyUpdate(BaseModel):
    max_eal_threshold_usd: float = Field(..., gt=0)
    max_var95_threshold_usd: float = Field(..., gt=0)
    max_cvar95_threshold_usd: float = Field(..., gt=0)
    remediation_sla_critical_days: int = Field(7, ge=1)
    remediation_sla_high_days: int = Field(30, ge=1)
    deduplication_window_hours: int = Field(24, ge=1)
    notify_email_recipients: Optional[List[str]] = None
    notify_webhook_urls: Optional[List[str]] = None


@router.get("/risk")
def get_risk_policy(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns active risk appetite thresholds and alerting policies."""
    policy = db.scalars(
        select(RiskPolicy).where(RiskPolicy.organization_id == current_org.id).order_by(RiskPolicy.version.desc())
    ).first()

    if not policy:
        # Default policy
        return {
            "version": 1,
            "max_eal_threshold_usd": 1_000_000.0,
            "max_var95_threshold_usd": 3_000_000.0,
            "max_cvar95_threshold_usd": 5_000_000.0,
            "remediation_sla_critical_days": 7,
            "remediation_sla_high_days": 30,
            "deduplication_window_hours": 24,
            "notify_email_recipients": [],
            "notify_webhook_urls": [],
        }

    return {
        "id": policy.id,
        "version": policy.version,
        "max_eal_threshold_usd": policy.max_eal_threshold_usd,
        "max_var95_threshold_usd": policy.max_var95_threshold_usd,
        "max_cvar95_threshold_usd": policy.max_cvar95_threshold_usd,
        "remediation_sla_critical_days": policy.remediation_sla_critical_days,
        "remediation_sla_high_days": policy.remediation_sla_high_days,
        "deduplication_window_hours": policy.deduplication_window_hours,
        "notify_email_recipients": policy.notify_email_recipients or [],
        "notify_webhook_urls": policy.notify_webhook_urls or [],
        "updated_at": policy.updated_at.isoformat(),
    }


@router.put("/risk")
def update_risk_policy(
    payload: RiskPolicyUpdate,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Updates organizational risk appetite thresholds and alert routing policies (admin/owner only)."""
    policy = db.scalars(
        select(RiskPolicy).where(RiskPolicy.organization_id == current_org.id).order_by(RiskPolicy.version.desc())
    ).first()

    if not policy:
        policy = RiskPolicy(
            organization_id=current_org.id,
            version=1,
            max_eal_threshold_usd=payload.max_eal_threshold_usd,
            max_var95_threshold_usd=payload.max_var95_threshold_usd,
            max_cvar95_threshold_usd=payload.max_cvar95_threshold_usd,
            remediation_sla_critical_days=payload.remediation_sla_critical_days,
            remediation_sla_high_days=payload.remediation_sla_high_days,
            deduplication_window_hours=payload.deduplication_window_hours,
            notify_email_recipients=payload.notify_email_recipients or [],
            notify_webhook_urls=payload.notify_webhook_urls or [],
        )
        db.add(policy)
    else:
        policy.max_eal_threshold_usd = payload.max_eal_threshold_usd
        policy.max_var95_threshold_usd = payload.max_var95_threshold_usd
        policy.max_cvar95_threshold_usd = payload.max_cvar95_threshold_usd
        policy.remediation_sla_critical_days = payload.remediation_sla_critical_days
        policy.remediation_sla_high_days = payload.remediation_sla_high_days
        policy.deduplication_window_hours = payload.deduplication_window_hours
        policy.notify_email_recipients = payload.notify_email_recipients or []
        policy.notify_webhook_urls = payload.notify_webhook_urls or []
        policy.version += 1

    db.commit()
    db.refresh(policy)
    return {"status": "success", "policy_version": policy.version}
