from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Asset, RegulatoryAssessment, RegulatoryRule, VulnerabilityFinding
from risk_engine.regulatory.rules import INDIAN_REGULATORY_RULES


class RegulatoryAssessmentEngine:
    """
    Evidence-based regulatory exposure engine for Indian cybersecurity regulations.
    Evaluates observed technical telemetry against verified statutory requirements.
    Distinguishes potential exposure scenarios from confirmed violations;
    statutory penalty caps are never misreported as expected or automatic fines.
    """

    def __init__(self, db: Session):
        self.db = db

    def sync_rules(self) -> None:
        """Ensures all standard regulatory rules are present in the database."""
        for rule_def in INDIAN_REGULATORY_RULES:
            existing = self.db.scalars(
                select(RegulatoryRule).where(
                    RegulatoryRule.instrument_id == rule_def["instrument_id"],
                    RegulatoryRule.version == rule_def["version"],
                )
            ).first()

            effective_from = datetime.fromisoformat(rule_def["effective_from"].replace("Z", "+00:00"))
            verified_date = datetime.fromisoformat(rule_def["verified_date"].replace("Z", "+00:00"))

            if not existing:
                rule = RegulatoryRule(
                    jurisdiction=rule_def["jurisdiction"],
                    framework_name=rule_def["framework_name"],
                    instrument_id=rule_def["instrument_id"],
                    provision_citation=rule_def["provision_citation"],
                    version=rule_def["version"],
                    title=rule_def["title"],
                    description=rule_def["description"],
                    applicability_criteria=rule_def["applicability_criteria"],
                    required_evidence=rule_def["required_evidence"],
                    statutory_penalty_max_usd=rule_def.get("statutory_penalty_max_usd"),
                    statutory_currency=rule_def.get("statutory_currency", "INR"),
                    effective_from=effective_from,
                    source_url=rule_def["source_url"],
                    verified_date=verified_date,
                    reviewer_status=rule_def["reviewer_status"],
                )
                self.db.add(rule)
        self.db.commit()

    def evaluate_dataset(
        self,
        dataset_id: str,
        dataset_version_id: str,
        run_id: Optional[str] = None,
    ) -> List[RegulatoryAssessment]:
        """
        Evaluates assets and vulnerability findings of a dataset against active regulatory rules.
        Creates RegulatoryAssessment records in DB.
        """
        self.sync_rules()

        # Query assets in dataset version
        assets = self.db.query(Asset).filter(Asset.dataset_version_id == dataset_version_id).all()
        findings = self.db.query(VulnerabilityFinding).filter(VulnerabilityFinding.dataset_version_id == dataset_version_id).all()

        rules = self.db.query(RegulatoryRule).all()
        assessments: List[RegulatoryAssessment] = []

        now = datetime.now(timezone.utc)

        # Count characteristics
        total_assets = len(assets)
        confidential_restricted_assets = [a for a in assets if a.data_sensitivity_tier in ("Confidential", "Restricted")]
        critical_vulns = [f for f in findings if f.cvss_score >= 9.0 or f.severity.lower() == "critical"]
        open_findings = [f for f in findings if f.status == "open"]

        for rule in rules:
            status = "not_applicable"
            affected_count = 0
            rationale = ""
            potential_min = None
            potential_max = None
            evidence_refs = []

            # 1. CERT-In Incident Reporting
            if "CERTIN-70B-INCIDENT-REPORTING" in rule.instrument_id:
                # If there are open critical vulnerabilities or incidents
                if critical_vulns:
                    status = "potential_exposure"
                    affected_count = len(critical_vulns)
                    potential_min = 0.0
                    potential_max = rule.statutory_penalty_max_usd
                    evidence_refs = [f"{f.cve_id} on asset {f.asset_id or 'unassigned'}" for f in critical_vulns[:5]]
                    rationale = (
                        f"{len(critical_vulns)} critical vulnerabilities detected. If an exploit causes a cyber incident, "
                        "mandatory reporting to CERT-In within 6 hours under Direction 2(i) is legally triggered. "
                        "Review whether any detected threat events represent reportable incidents."
                    )
                else:
                    status = "needs_review"
                    rationale = "No confirmed incidents currently logged. Ensure 6-hour CERT-In reporting channel is operational."

            # 2. CERT-In 180-Day Log Retention
            elif "LOG-RETENTION" in rule.instrument_id:
                status = "gap"
                affected_count = total_assets
                evidence_refs = ["SIEM configuration", "Log archive retention settings"]
                rationale = (
                    "Mandatory 180-day ICT log retention requirement within Indian jurisdiction applies to all enterprise systems. "
                    "Verification required by compliance auditor to confirm logs are retained for >= 180 days."
                )

            # 3. DPDP Act Section 8(5) - Reasonable Security Safeguards
            elif "DPDP-ACT-2023-SEC-8-5" in rule.instrument_id:
                if confidential_restricted_assets:
                    affected_count = len(confidential_restricted_assets)
                    evidence_refs = [f"Asset {a.asset_key} ({a.data_sensitivity_tier})" for a in confidential_restricted_assets[:5]]
                    if critical_vulns:
                        status = "potential_exposure"
                        potential_min = 0.0
                        potential_max = rule.statutory_penalty_max_usd  # statutory cap (up to 250 Cr INR)
                        rationale = (
                            f"{len(confidential_restricted_assets)} assets store Confidential/Restricted personal data, "
                            f"with {len(critical_vulns)} active critical vulnerabilities. Section 8(5) requires reasonable "
                            "safeguards to prevent personal data breach. Statutory maximum cap is ₹250 Cr; actual liability "
                            "depends on adjudication factors under DPDP Act Section 33(2). Human review required."
                        )
                    else:
                        status = "needs_review"
                        rationale = f"{len(confidential_restricted_assets)} sensitive data assets identified. Safeguards in place require formal annual audit."
                else:
                    status = "not_applicable"
                    rationale = "No assets marked as Confidential or Restricted personal data tiers in this dataset."

            # 4. DPDP Act Section 8(6) - Breach Notification
            elif "DPDP-ACT-2023-SEC-8-6" in rule.instrument_id:
                if confidential_restricted_assets and critical_vulns:
                    status = "potential_exposure"
                    affected_count = len(confidential_restricted_assets)
                    potential_min = 0.0
                    potential_max = rule.statutory_penalty_max_usd
                    rationale = (
                        "In case of a personal data breach involving these assets, Section 8(6) mandates intimation to the "
                        "Data Protection Board and Data Principals. Statutory cap under Schedule is up to ₹200 Cr. Factual verification required."
                    )
                else:
                    status = "not_applicable"
                    rationale = "No confirmed personal data breach currently established from technical telemetry alone."

            # 5. RBI Master Directions
            elif "RBI" in rule.instrument_id:
                status = "needs_review"
                affected_count = total_assets
                rationale = "Applicable if organization is a Bank, NBFC or Payment System Operator under RBI jurisdiction. Requires compliance review."

            # 6. SEBI CSCRF
            elif "SEBI" in rule.instrument_id:
                status = "needs_review"
                affected_count = total_assets
                rationale = "Applicable to Qualified Regulated Entities in capital markets. Requires confirmation of regulated status."

            assessment = self._upsert_assessment(
                dataset_id=dataset_id,
                run_id=run_id,
                rule=rule,
                status=status,
                affected_count=affected_count,
                evidence_refs=evidence_refs,
                potential_min=potential_min,
                potential_max=potential_max,
                rationale=rationale,
                now=now,
            )
            assessments.append(assessment)

        self.db.commit()
        return assessments

    def _upsert_assessment(
        self,
        dataset_id: str,
        run_id: Optional[str],
        rule: RegulatoryRule,
        status: str,
        affected_count: int,
        evidence_refs: list,
        potential_min: Optional[float],
        potential_max: Optional[float],
        rationale: str,
        now: datetime,
    ) -> RegulatoryAssessment:
        """
        Creates or refreshes the assessment for (dataset, rule).

        A human-reviewed assessment is never silently overwritten by a later
        automated evaluation; the reviewer decision is preserved and only the
        run reference is updated.
        """
        existing = self.db.scalars(
            select(RegulatoryAssessment).where(
                RegulatoryAssessment.dataset_id == dataset_id,
                RegulatoryAssessment.rule_id == rule.id,
            )
        ).first()

        if existing is None:
            assessment = RegulatoryAssessment(
                dataset_id=dataset_id,
                run_id=run_id,
                rule_id=rule.id,
                status=status,
                affected_assets_count=affected_count,
                evidence_refs=evidence_refs,
                potential_exposure_min_usd=potential_min,
                potential_exposure_max_usd=potential_max,
                rationale=rationale,
                created_at=now,
            )
            self.db.add(assessment)
            return assessment

        existing.run_id = run_id or existing.run_id
        if existing.status not in ("reviewed", "accepted_risk"):
            existing.status = status
            existing.affected_assets_count = affected_count
            existing.evidence_refs = evidence_refs
            existing.potential_exposure_min_usd = potential_min
            existing.potential_exposure_max_usd = potential_max
            existing.rationale = rationale
        return existing
