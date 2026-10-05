import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    default_currency = Column(String(10), nullable=False, default="USD")
    risk_appetite_thresholds = Column(JSON, nullable=True)
    policy_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="organization", cascade="all, delete-orphan")
    alerts = relationship("RiskAlert", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
    policies = relationship("RiskPolicy", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    refresh_sessions = relationship("RefreshSession", back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="analyst")  # owner, admin, analyst, viewer
    created_at = Column(DateTime, default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user_membership"),
    )


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(64), nullable=False, index=True)
    family_id = Column(String(36), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    rotated_at = Column(DateTime, nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)

    user = relationship("User", back_populates="refresh_sessions")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    active_version_id = Column(String(36), nullable=True)
    dataset_type = Column(String(50), nullable=False, default="tabular")  # tabular, scanner_enriched, demo
    status = Column(String(50), nullable=False, default="active")  # active, archived
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="datasets")
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")
    runs = relationship("RiskRun", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    source_checksum = Column(String(64), nullable=True)
    row_counts = Column(JSON, nullable=True)
    validation_report = Column(JSON, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")
    time_window_days = Column(Float, nullable=False, default=30.0)
    is_valid = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    dataset = relationship("Dataset", back_populates="versions")
    artifacts = relationship("SourceArtifact", back_populates="version", cascade="all, delete-orphan")
    runs = relationship("RiskRun", back_populates="version")


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_key = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    detected_format = Column(String(50), nullable=False)  # csv, zip, json, excel, openvas_xml, nessus_json, appsec_csv
    sha256_hash = Column(String(64), nullable=False)
    byte_size = Column(Integer, nullable=False)
    uploader_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    parser_version = Column(String(50), nullable=True)
    retention_state = Column(String(50), default="retained", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    version = relationship("DatasetVersion", back_populates="artifacts")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True, index=True)
    version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    task_type = Column(String(50), nullable=False)  # ingestion, scan_import, risk_run, ml_train, threat_intel
    idempotency_key = Column(String(255), nullable=True, index=True)
    state = Column(String(50), default="queued", nullable=False)  # queued, running, succeeded, failed
    progress_pct = Column(Float, default=0.0, nullable=False)
    result_summary = Column(JSON, nullable=True)
    safe_error_code = Column(String(100), nullable=True)
    safe_error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_key = Column(String(100), nullable=False, index=True)
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    business_unit = Column(String(100), nullable=False)
    criticality = Column(Integer, nullable=False, default=3)  # 1-5
    data_sensitivity_tier = Column(String(50), nullable=False, default="Internal")
    currency = Column(String(10), nullable=False, default="USD")
    financial_value_usd = Column(Float, nullable=False, default=0.0)
    downtime_cost_per_hour_usd = Column(Float, nullable=False, default=0.0)
    regulatory_penalty_potential_usd = Column(Float, nullable=False, default=0.0)
    os = Column(String(100), nullable=True)
    internet_exposed = Column(Boolean, default=False, nullable=False)
    owner = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_asset_ver_key", "dataset_version_id", "asset_key"),
    )


class VulnerabilityFinding(Base):
    __tablename__ = "vulnerability_findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    scanner_source = Column(String(50), nullable=False, default="csv")  # openvas, nessus, appsec, csv
    source_finding_id = Column(String(255), nullable=True)
    cve_id = Column(String(50), nullable=False, index=True)
    product_name = Column(String(255), nullable=True)
    package_name = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    protocol = Column(String(20), nullable=True)
    cvss_version = Column(String(10), nullable=True, default="3.1")
    cvss_vector = Column(String(200), nullable=True)
    cvss_score = Column(Float, nullable=False, default=0.0)
    epss_score = Column(Float, nullable=True)
    severity = Column(String(20), nullable=False, default="Medium")
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    match_status = Column(String(50), nullable=False, default="matched")  # matched, unmatched, pending_review, rejected
    status = Column(String(50), nullable=False, default="open")  # open, patched, remediated, accepted
    evidence_ref = Column(Text, nullable=True)
    parser_version = Column(String(50), nullable=True)
    dedupe_fingerprint = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ThreatEvent(Base):
    __tablename__ = "threat_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=True, index=True)
    event_id = Column(String(100), nullable=False)
    observed_at = Column(DateTime, nullable=False)
    source = Column(String(100), nullable=True)
    mitre_technique_id = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="Medium")
    source_ip = Column(String(50), nullable=True)
    action_taken = Column(String(100), nullable=True)
    downtime_hours_caused = Column(Float, default=0.0, nullable=False)
    records_compromised = Column(Integer, default=0, nullable=False)
    source_type = Column(String(50), default="observed", nullable=False)  # observed, synthetic_demo
    evidence_ref = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class SecurityControl(Base):
    __tablename__ = "security_controls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    catalog_id = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="Preventive")
    cost_usd = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="USD")
    risk_reduction_pct = Column(Float, nullable=False, default=0.0)
    target_component = Column(String(50), nullable=True)
    dependencies = Column(JSON, nullable=True)
    evidence_source = Column(String(255), nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)


class AssetControl(Base):
    __tablename__ = "asset_controls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    control_id = Column(String(36), ForeignKey("security_controls.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)
    deployment_date = Column(DateTime, nullable=True)
    effectiveness_evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class ThreatIntelSnapshot(Base):
    __tablename__ = "threat_intel_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    cve_id = Column(String(50), nullable=False, index=True)
    source = Column(String(50), nullable=False)  # epss, cisa_kev
    score = Column(Float, nullable=True)
    percentile = Column(Float, nullable=True)
    is_known_exploited = Column(Boolean, default=False, nullable=False)
    kev_date_added = Column(DateTime, nullable=True)
    kev_due_date = Column(DateTime, nullable=True)
    kev_required_action = Column(Text, nullable=True)
    source_publication_date = Column(DateTime, nullable=True)
    source_version = Column(String(50), nullable=True)
    response_hash = Column(String(64), nullable=True)
    status = Column(String(50), default="fresh", nullable=False)  # fresh, stale, unavailable
    fetched_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_cve_source", "cve_id", "source"),
    )


class RiskRun(Base):
    __tablename__ = "risk_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_version_id = Column(String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    config_version = Column(String(50), nullable=False, default="1.0.0")
    model_version = Column(String(50), nullable=False, default="fair-v2.1")
    code_version = Column(String(50), nullable=False, default="1.0.0")
    rng_seed = Column(Integer, nullable=False, default=42)
    threat_intel_snapshot_refs = Column(JSON, nullable=True)
    state = Column(String(50), default="queued", nullable=False)  # queued, running, completed, failed
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    input_hash = Column(String(64), nullable=True)
    summary_metrics = Column(JSON, nullable=True)
    artifact_base_path = Column(String(500), nullable=True)
    safe_error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    organization = relationship("Organization")
    dataset = relationship("Dataset", back_populates="runs")
    version = relationship("DatasetVersion", back_populates="runs")
    asset_results = relationship("AssetRiskResult", back_populates="run", cascade="all, delete-orphan")
    portfolio_results = relationship("PortfolioRiskResult", back_populates="run", cascade="all, delete-orphan")
    scenarios = relationship("ControlScenario", back_populates="run", cascade="all, delete-orphan")


class AssetRiskResult(Base):
    __tablename__ = "asset_risk_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_key = Column(String(100), nullable=False)
    eal_usd = Column(Float, nullable=False, default=0.0)
    var95_usd = Column(Float, nullable=False, default=0.0)
    var99_usd = Column(Float, nullable=False, default=0.0)
    cvar95_usd = Column(Float, nullable=False, default=0.0)
    primary_loss_usd = Column(Float, nullable=False, default=0.0)
    secondary_loss_usd = Column(Float, nullable=False, default=0.0)
    sample_count = Column(Integer, nullable=False, default=20000)
    confidence_status = Column(String(50), default="high", nullable=False)  # high, moderate, low, sparse_telemetry
    drivers = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("RiskRun", back_populates="asset_results")


class PortfolioRiskResult(Base):
    __tablename__ = "portfolio_risk_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_key = Column(String(500), nullable=True)
    total_eal_usd = Column(Float, nullable=False, default=0.0)
    total_var95_usd = Column(Float, nullable=False, default=0.0)
    total_var99_usd = Column(Float, nullable=False, default=0.0)
    total_cvar95_usd = Column(Float, nullable=False, default=0.0)
    max_probable_loss_usd = Column(Float, nullable=True)
    dependence_assumptions = Column(JSON, nullable=True)
    currency = Column(String(10), nullable=False, default="USD")
    summary_metrics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("RiskRun", back_populates="portfolio_results")


class ControlScenario(Base):
    __tablename__ = "control_scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    control_id = Column(String(36), ForeignKey("security_controls.id", ondelete="CASCADE"), nullable=False, index=True)
    control_name = Column(String(255), nullable=False)
    cost_usd = Column(Float, nullable=False, default=0.0)
    eal_before_usd = Column(Float, nullable=False, default=0.0)
    eal_after_usd = Column(Float, nullable=False, default=0.0)
    risk_reduction_usd = Column(Float, nullable=False, default=0.0)
    rosi = Column(Float, nullable=False, default=0.0)
    selection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("RiskRun", back_populates="scenarios")


class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    jurisdiction = Column(String(10), nullable=False, default="IN")
    framework_name = Column(String(50), nullable=False)  # CERT-In, DPDP, RBI, SEBI
    instrument_id = Column(String(100), nullable=False)
    provision_citation = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False, default="2025.1")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    applicability_criteria = Column(JSON, nullable=True)
    required_evidence = Column(JSON, nullable=True)
    statutory_penalty_max_usd = Column(Float, nullable=True)
    statutory_currency = Column(String(10), nullable=False, default="INR")
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    source_url = Column(String(500), nullable=False)
    verified_date = Column(DateTime, nullable=False)
    reviewer_status = Column(String(50), nullable=False, default="verified")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    assessments = relationship("RegulatoryAssessment", back_populates="rule")


class RegulatoryAssessment(Base):
    __tablename__ = "regulatory_assessments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(String(36), ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    rule_id = Column(String(36), ForeignKey("regulatory_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="needs_review")  # not_applicable, gap, potential_exposure, needs_review, reviewed
    affected_assets_count = Column(Integer, default=0, nullable=False)
    evidence_refs = Column(JSON, nullable=True)
    potential_exposure_min_usd = Column(Float, nullable=True)
    potential_exposure_max_usd = Column(Float, nullable=True)
    deadline_at = Column(DateTime, nullable=True)
    rationale = Column(Text, nullable=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    rule = relationship("RegulatoryRule", back_populates="assessments")


class RiskPolicy(Base):
    __tablename__ = "risk_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    max_eal_threshold_usd = Column(Float, nullable=False, default=1_000_000.0)
    max_var95_threshold_usd = Column(Float, nullable=False, default=3_000_000.0)
    max_cvar95_threshold_usd = Column(Float, nullable=False, default=5_000_000.0)
    remediation_sla_critical_days = Column(Integer, default=7, nullable=False)
    remediation_sla_high_days = Column(Integer, default=30, nullable=False)
    deduplication_window_hours = Column(Integer, default=24, nullable=False)
    notify_email_recipients = Column(JSON, nullable=True)
    notify_webhook_urls = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="policies")


class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id = Column(String(36), ForeignKey("risk_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    policy_id = Column(String(36), ForeignKey("risk_policies.id", ondelete="SET NULL"), nullable=True)
    severity = Column(String(20), nullable=False)  # critical, high, medium, low
    category = Column(String(50), nullable=False)  # kev_critical_asset, risk_appetite_breach, sla_breach, compliance_gap, model_anomaly
    dedupe_key = Column(String(255), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    evidence_refs = Column(JSON, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="open", nullable=False)  # open, acknowledged, in_progress, resolved, closed, reopened
    opened_at = Column(DateTime, default=utc_now, nullable=False)
    due_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="alerts")
    deliveries = relationship("AlertDelivery", back_populates="alert", cascade="all, delete-orphan")


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    alert_id = Column(String(36), ForeignKey("risk_alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), nullable=False)  # email, webhook
    recipient = Column(String(255), nullable=False)
    state = Column(String(50), default="queued", nullable=False)  # queued, sent, failed, simulated
    attempts = Column(Integer, default=0, nullable=False)
    provider_ref = Column(String(255), nullable=True)
    sanitized_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    alert = relationship("RiskAlert", back_populates="deliveries")


class RemediationTask(Base):
    __tablename__ = "remediation_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(String(36), ForeignKey("risk_alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    finding_id = Column(String(36), ForeignKey("vulnerability_findings.id", ondelete="SET NULL"), nullable=True, index=True)
    control_id = Column(String(36), ForeignKey("security_controls.id", ondelete="SET NULL"), nullable=True, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    priority = Column(String(20), nullable=False, default="medium")  # critical, high, medium, low
    due_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="todo", nullable=False)  # todo, in_progress, review, completed, cancelled
    action_notes = Column(Text, nullable=True)
    verification_evidence = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)

    organization = relationship("Organization", back_populates="audit_events")
