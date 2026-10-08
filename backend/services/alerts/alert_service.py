import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import ConflictError, ResourceNotFoundError
from db.models import (
    Asset,
    AssetRiskResult,
    PortfolioRiskResult,
    RiskAlert,
    RiskPolicy,
    VulnerabilityFinding,
)
from services.alerts.delivery import NotificationDeliveryService


SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class AlertService:
    def __init__(self, db: Session):
        self.db = db
        self.delivery_service = NotificationDeliveryService(db)

    def evaluate_risk_run_alerts(self, run_id: str, org_id: str, dataset_id: str) -> List[RiskAlert]:
        """Evaluates policy thresholds and technical evidence following a RiskRun, generating alerts."""
        # Get active organization policy
        policy = self.db.scalars(
            select(RiskPolicy).where(RiskPolicy.organization_id == org_id).order_by(RiskPolicy.version.desc())
        ).first()

        max_eal = policy.max_eal_threshold_usd if policy else 1_000_000.0
        max_var95 = policy.max_var95_threshold_usd if policy else 3_000_000.0
        sla_critical = policy.remediation_sla_critical_days if policy else 7
        sla_high = policy.remediation_sla_high_days if policy else 30
        dedupe_hours = policy.deduplication_window_hours if policy else 24
        recipients = policy.notify_email_recipients if policy else []
        webhooks = policy.notify_webhook_urls if policy else []

        now = datetime.now(timezone.utc)
        created_alerts: List[RiskAlert] = []

        # 1. Check Portfolio Risk Appetite Thresholds
        portfolio = self.db.scalars(
            select(PortfolioRiskResult).where(PortfolioRiskResult.run_id == run_id)
        ).first()

        if portfolio:
            if portfolio.total_eal_usd > max_eal:
                dedupe_key = hashlib.sha256(f"{org_id}:eal_breach:{dataset_id}".encode("utf-8")).hexdigest()
                alert = self._upsert_alert(
                    org_id=org_id,
                    dataset_id=dataset_id,
                    run_id=run_id,
                    policy_id=policy.id if policy else None,
                    severity="critical" if portfolio.total_eal_usd > max_eal * 1.5 else "high",
                    category="risk_appetite_breach",
                    dedupe_key=dedupe_key,
                    title="Portfolio EAL Exceeds Organization Risk Appetite",
                    description=(
                        f"Simulated Expected Annual Loss of ${portfolio.total_eal_usd:,.2f} USD "
                        f"exceeds the authorized threshold of ${max_eal:,.2f} USD."
                    ),
                    evidence_refs=[f"EAL: ${portfolio.total_eal_usd:,.2f}", f"Threshold: ${max_eal:,.2f}"],
                    due_at=now + timedelta(days=sla_critical),
                    dedupe_hours=dedupe_hours,
                )
                if alert:
                    created_alerts.append(alert)

            if portfolio.total_var95_usd > max_var95:
                dedupe_key = hashlib.sha256(f"{org_id}:var_breach:{dataset_id}".encode("utf-8")).hexdigest()
                alert = self._upsert_alert(
                    org_id=org_id,
                    dataset_id=dataset_id,
                    run_id=run_id,
                    policy_id=policy.id if policy else None,
                    severity="high",
                    category="risk_appetite_breach",
                    dedupe_key=dedupe_key,
                    title="Portfolio VaR95 Exceeds Tolerance Limit",
                    description=(
                        f"Simulated Value at Risk (95th percentile) of ${portfolio.total_var95_usd:,.2f} USD "
                        f"exceeds tolerance of ${max_var95:,.2f} USD."
                    ),
                    evidence_refs=[f"VaR95: ${portfolio.total_var95_usd:,.2f}", f"Threshold: ${max_var95:,.2f}"],
                    due_at=now + timedelta(days=sla_high),
                    dedupe_hours=dedupe_hours,
                )
                if alert:
                    created_alerts.append(alert)

        # 2. Check for CISA KEV on Critical Assets
        findings = self.db.query(VulnerabilityFinding).join(
            Asset, VulnerabilityFinding.asset_id == Asset.id
        ).filter(
            VulnerabilityFinding.status == "open",
            Asset.criticality >= 4,
        ).all()

        for f in findings:
            # Check if flagged as KEV or CVSS >= 9.0
            if f.cvss_score >= 9.0 or (f.evidence_ref and "KEV" in f.evidence_ref):
                dedupe_key = hashlib.sha256(f"{org_id}:kev_critical:{f.asset_id}:{f.cve_id}".encode("utf-8")).hexdigest()
                alert = self._upsert_alert(
                    org_id=org_id,
                    dataset_id=dataset_id,
                    run_id=run_id,
                    policy_id=policy.id if policy else None,
                    severity="critical",
                    category="kev_critical_asset",
                    dedupe_key=dedupe_key,
                    title=f"Critical Exploit Exposure: {f.cve_id} on Tier-1 Asset",
                    description=(
                        f"Critical vulnerability {f.cve_id} (CVSS {f.cvss_score:.1f}) is open on "
                        f"criticality-{f.asset_id} asset. Immediate remediation required under policy SLA."
                    ),
                    evidence_refs=[f"CVE: {f.cve_id}", f"CVSS: {f.cvss_score}", f"Asset: {f.asset_id}"],
                    due_at=now + timedelta(days=sla_critical),
                    dedupe_hours=dedupe_hours,
                )
                if alert:
                    created_alerts.append(alert)

        # Dispatch notifications for new/reopened alerts
        for alert in created_alerts:
            self.delivery_service.dispatch_alert(alert, recipients=recipients, webhooks=webhooks)

        return created_alerts

    def _upsert_alert(
        self,
        org_id: str,
        dataset_id: Optional[str],
        run_id: Optional[str],
        policy_id: Optional[str],
        severity: str,
        category: str,
        dedupe_key: str,
        title: str,
        description: str,
        evidence_refs: list,
        due_at: Optional[datetime],
        dedupe_hours: int = 24,
    ) -> Optional[RiskAlert]:
        """
        Deduplicates against open/acknowledged alerts matching dedupe_key within time window.
        If existing alert is closed but material change occurred (e.g. severity escalated), reopens alert.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=dedupe_hours)

        existing = self.db.scalars(
            select(RiskAlert).where(
                RiskAlert.organization_id == org_id,
                RiskAlert.dedupe_key == dedupe_key,
            ).order_by(RiskAlert.created_at.desc())
        ).first()

        if existing:
            # Handle naive datetime
            c_at = existing.created_at
            if c_at.tzinfo is None:
                c_at = c_at.replace(tzinfo=timezone.utc)

            if existing.status in ("open", "acknowledged", "in_progress") and c_at >= cutoff:
                # Update existing alert with latest run and evidence
                existing.run_id = run_id
                existing.evidence_refs = evidence_refs
                existing.updated_at = now
                self.db.commit()
                return None  # Deduplicated, no new notification needed

            if existing.status in ("resolved", "closed"):
                # Reopen if problem persists
                existing.status = "reopened"
                existing.severity = severity
                existing.run_id = run_id
                existing.description = description
                existing.evidence_refs = evidence_refs
                existing.updated_at = now
                self.db.commit()
                return existing

        # Create brand new alert
        alert = RiskAlert(
            organization_id=org_id,
            dataset_id=dataset_id,
            run_id=run_id,
            policy_id=policy_id,
            severity=severity,
            category=category,
            dedupe_key=dedupe_key,
            title=title,
            description=description,
            evidence_refs=evidence_refs,
            status="open",
            opened_at=now,
            due_at=due_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def transition_status(
        self,
        alert_id: str,
        new_status: str,
        actor_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> RiskAlert:
        """Transitions alert lifecycle: open, acknowledged, in_progress, resolved, closed.

        When ``org_id`` is provided the lookup is scoped to that organization so a
        cross-tenant alert id behaves as if it does not exist.
        """
        valid_statuses = ("open", "acknowledged", "in_progress", "resolved", "closed", "reopened")
        if new_status not in valid_statuses:
            raise ConflictError(message=f"Invalid alert status: {new_status}")

        query = select(RiskAlert).where(RiskAlert.id == alert_id)
        if org_id is not None:
            query = query.where(RiskAlert.organization_id == org_id)
        alert = self.db.scalars(query).first()
        if not alert:
            raise ResourceNotFoundError(message="Alert not found")

        now = datetime.now(timezone.utc)
        alert.status = new_status
        alert.updated_at = now
        if new_status == "closed":
            alert.closed_at = now

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def assign_owner(self, alert_id: str, owner_id: str, org_id: Optional[str] = None) -> RiskAlert:
        """Assigns an alert to a team member (optionally scoped to an organization)."""
        query = select(RiskAlert).where(RiskAlert.id == alert_id)
        if org_id is not None:
            query = query.where(RiskAlert.organization_id == org_id)
        alert = self.db.scalars(query).first()
        if not alert:
            raise ResourceNotFoundError(message="Alert not found")

        alert.owner_id = owner_id
        alert.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(alert)
        return alert
