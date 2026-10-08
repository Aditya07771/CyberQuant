import hashlib
import json
import logging
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.errors import BadInputError, ResourceNotFoundError
from db.models import (
    Asset,
    AssetControl,
    AssetRiskResult,
    ControlScenario,
    Dataset,
    DatasetVersion,
    PortfolioRiskResult,
    RiskPolicy,
    RiskRun,
    SecurityControl,
    SourceArtifact,
    ThreatEvent,
    VulnerabilityFinding,
)
from integrations.threat_intel.service import ThreatIntelService
from risk_engine.config import EngineConfig
from risk_engine.excel_mapper import build_excel_summary, is_card_dataset, map_cards_to_risk_tables
from risk_engine.ingest import DataIngestor, IngestionError
from risk_engine.pipeline import RiskPipeline
from risk_engine.regulatory.engine import RegulatoryAssessmentEngine
from risk_engine.scanners import AppSecCSVParser, NessusParser, OpenVASParser, ScanNormalizer
from services.alerts.alert_service import AlertService

logger = logging.getLogger(__name__)

REQUIRED_TABLES = ["assets", "vulnerabilities", "threat_events", "controls", "asset_controls"]

REQUIRED_COLUMNS = {
    "assets": ["asset_id", "business_unit", "criticality", "data_sensitivity_tier", "financial_value_usd", "downtime_cost_per_hour_usd"],
    "controls": ["control_id", "name", "risk_reduction_pct", "cost_usd"],
    "asset_controls": ["asset_id", "control_id"],
    "threat_events": ["event_id", "asset_id", "downtime_hours_caused", "records_compromised"],
    "vulnerabilities": ["asset_id", "cve_id", "cvss_score", "epss_score"],
}


class DatasetService:
    def __init__(self, db: Session):
        self.db = db

    def get_run_output_dir(self, org_id: str, dataset_id: str, run_id: str) -> Path:
        """Returns the isolated, server-controlled path for run outputs."""
        path = settings.OUTPUT_BASE_DIR / org_id / dataset_id / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def validate_tables(self, data: Dict[str, pd.DataFrame]) -> None:
        """Strict domain and schema validation for the 5 risk tables."""
        missing = [t for t in REQUIRED_TABLES if t not in data or data[t] is None]
        if missing:
            raise BadInputError(message=f"Missing required datasets: {', '.join(missing)}")

        for table, req_cols in REQUIRED_COLUMNS.items():
            df = data[table]
            if df.empty and table in ("assets", "controls"):
                raise BadInputError(message=f"Dataset '{table}.csv' cannot be empty")
            missing_cols = [c for c in req_cols if c not in df.columns]
            if missing_cols:
                raise BadInputError(message=f"Missing columns in '{table}.csv': {', '.join(missing_cols)}")

        # Numeric validations
        assets_df = data["assets"]
        if (pd.to_numeric(assets_df["financial_value_usd"], errors="coerce") < 0).any():
            raise BadInputError(message="Negative financial_value_usd found in assets.csv")
        if (pd.to_numeric(assets_df["downtime_cost_per_hour_usd"], errors="coerce") < 0).any():
            raise BadInputError(message="Negative downtime_cost_per_hour_usd found in assets.csv")

        controls_df = data["controls"]
        rr_pct = pd.to_numeric(controls_df["risk_reduction_pct"], errors="coerce")
        if (rr_pct > 1.0).any() or (rr_pct < 0.0).any() or rr_pct.isna().any():
            raise BadInputError(message="risk_reduction_pct in controls.csv must be between 0.0 and 1.0")

        cost = pd.to_numeric(controls_df["cost_usd"], errors="coerce")
        if (cost < 0).any() or cost.isna().any():
            raise BadInputError(message="cost_usd in controls.csv must be non-negative")

        # Range check on CVSS/EPSS
        vulns_df = data["vulnerabilities"]
        cvss = pd.to_numeric(vulns_df["cvss_score"], errors="coerce")
        if (cvss < 0).any() or (cvss > 10).any():
            raise BadInputError(message="cvss_score in vulnerabilities.csv must be between 0.0 and 10.0")

        epss = pd.to_numeric(vulns_df["epss_score"], errors="coerce").dropna()
        if (epss < 0).any() or (epss > 1.0).any():
            raise BadInputError(message="epss_score in vulnerabilities.csv must be between 0.0 and 1.0")

    def create_dataset_version(
        self,
        dataset: Dataset,
        data: Dict[str, pd.DataFrame],
        uploader_id: Optional[str] = None,
        source_format: str = "csv_bundle",
        excel_summary: Optional[dict] = None,
        version: Optional[DatasetVersion] = None,
    ) -> DatasetVersion:
        """Stores dataset version, artifacts, and loads rows into relational tables.

        When ``version`` is supplied the pre-created (pending) version row is
        populated instead of inserting a new record, so the upload endpoint can
        return a ``version_id`` in its 202 response.
        """
        self.validate_tables(data)

        now = datetime.now(timezone.utc)
        row_counts = {t: len(df) for t, df in data.items()}

        # Compute checksum of combined datasets
        hasher = hashlib.sha256()
        for t in sorted(data.keys()):
            hasher.update(data[t].to_csv(index=False).encode("utf-8"))
        checksum = hasher.hexdigest()

        if version is None:
            prev_versions = self.db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset.id).count()
            version_num = prev_versions + 1
            version = DatasetVersion(
                dataset_id=dataset.id,
                version_number=version_num,
                source_checksum=checksum,
                row_counts=row_counts,
                validation_report={"status": "valid", "excel_summary": excel_summary},
                currency="USD",
                time_window_days=30.0,
                is_valid=True,
                created_at=now,
            )
            self.db.add(version)
        else:
            version.source_checksum = checksum
            version.row_counts = row_counts
            version.validation_report = {"status": "valid", "excel_summary": excel_summary}
            version.is_valid = True
        self.db.flush()

        dataset.active_version_id = version.id
        dataset.updated_at = now

        # Save table files to server storage
        storage_base = settings.DATA_BASE_DIR / "tenants" / dataset.organization_id / dataset.id / version.id
        storage_base.mkdir(parents=True, exist_ok=True)

        for name, df in data.items():
            csv_path = storage_base / f"{name}.csv"
            df.to_csv(csv_path, index=False)
            file_bytes = csv_path.read_bytes()
            artifact = SourceArtifact(
                dataset_id=dataset.id,
                version_id=version.id,
                storage_key=str(csv_path.relative_to(settings.DATA_BASE_DIR)),
                original_filename=f"{name}.csv",
                detected_format=source_format,
                sha256_hash=hashlib.sha256(file_bytes).hexdigest(),
                byte_size=len(file_bytes),
                uploader_id=uploader_id,
                created_at=now,
            )
            self.db.add(artifact)

        # Populate relational tables for this version
        assets_df = data["assets"]
        asset_map: Dict[str, Asset] = {}
        for _, r in assets_df.iterrows():
            a = Asset(
                dataset_version_id=version.id,
                asset_key=str(r["asset_id"]),
                hostname=str(r.get("hostname", r["asset_id"])),
                ip_address=str(r.get("ip_address", "")),
                business_unit=str(r["business_unit"]),
                criticality=int(r.get("criticality", 3)),
                data_sensitivity_tier=str(r.get("data_sensitivity_tier", "Internal")),
                currency="USD",
                financial_value_usd=float(r.get("financial_value_usd", 0.0)),
                downtime_cost_per_hour_usd=float(r.get("downtime_cost_per_hour_usd", 0.0)),
                regulatory_penalty_potential_usd=float(r.get("regulatory_penalty_potential_usd", 0.0)),
                os=str(r.get("os", "Linux")),
                created_at=now,
            )
            self.db.add(a)
            self.db.flush()
            asset_map[str(r["asset_id"])] = a

        # Vulnerabilities
        vulns_df = data["vulnerabilities"]
        for _, r in vulns_df.iterrows():
            aid = str(r["asset_id"])
            matched_asset = asset_map.get(aid)
            v = VulnerabilityFinding(
                dataset_version_id=version.id,
                asset_id=matched_asset.id if matched_asset else None,
                scanner_source="tabular_csv",
                cve_id=str(r["cve_id"]).upper(),
                cvss_score=float(r.get("cvss_score", 0.0)),
                epss_score=float(r["epss_score"]) if pd.notna(r.get("epss_score")) else None,
                severity=str(r.get("severity", "Medium")),
                status=str(r.get("status", "open")),
                match_status="matched" if matched_asset else "unmatched",
                first_seen=now,
                last_seen=now,
                created_at=now,
            )
            self.db.add(v)

        # Threat Events
        events_df = data["threat_events"]
        # Built-in/demo bundles contain simulated telemetry and must not be
        # presented as observed production events.
        event_source_type = "synthetic_demo" if dataset.dataset_type == "demo" else "observed"
        for _, r in events_df.iterrows():
            aid = str(r["asset_id"])
            matched_asset = asset_map.get(aid)
            obs_at = now
            if pd.notna(r.get("timestamp")):
                try:
                    obs_at = pd.to_datetime(r["timestamp"]).to_pydatetime()
                    if obs_at.tzinfo is None:
                        obs_at = obs_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            te = ThreatEvent(
                dataset_version_id=version.id,
                asset_id=matched_asset.id if matched_asset else None,
                event_id=str(r["event_id"]),
                observed_at=obs_at,
                source=str(r.get("source", "SIEM")),
                mitre_technique_id=str(r.get("mitre_technique_id", "T1059")),
                description=str(r.get("description", "")),
                severity=str(r.get("severity", "Medium")),
                source_ip=str(r.get("source_ip", "")),
                action_taken=str(r.get("action_taken", "blocked")),
                downtime_hours_caused=float(r.get("downtime_hours_caused", 0.0)),
                records_compromised=int(r.get("records_compromised", 0)),
                source_type=event_source_type,
                created_at=now,
            )
            self.db.add(te)

        # Controls Catalog
        controls_df = data["controls"]
        ctrl_map: Dict[str, SecurityControl] = {}
        for _, r in controls_df.iterrows():
            cid = str(r["control_id"])
            existing_ctrl = self.db.scalars(select(SecurityControl).where(SecurityControl.catalog_id == cid)).first()
            if not existing_ctrl:
                ctrl = SecurityControl(
                    catalog_id=cid,
                    name=str(r["name"]),
                    category="Mitigation",
                    cost_usd=float(r.get("cost_usd", 0.0)),
                    currency="USD",
                    risk_reduction_pct=float(r.get("risk_reduction_pct", 0.0)),
                )
                self.db.add(ctrl)
                self.db.flush()
                ctrl_map[cid] = ctrl
            else:
                ctrl_map[cid] = existing_ctrl

        # Asset Controls
        ac_df = data["asset_controls"]
        for _, r in ac_df.iterrows():
            aid = str(r["asset_id"])
            cid = str(r["control_id"])
            matched_asset = asset_map.get(aid)
            matched_ctrl = ctrl_map.get(cid)
            if matched_asset and matched_ctrl:
                ac = AssetControl(
                    dataset_version_id=version.id,
                    asset_id=matched_asset.id,
                    control_id=matched_ctrl.id,
                    status="active",
                    created_at=now,
                )
                self.db.add(ac)

        self.db.commit()
        self.db.refresh(version)
        return version

    def execute_risk_run(
        self,
        dataset_id: str,
        org_id: str,
        user_id: Optional[str] = None,
        rng_seed: int = 42,
        n_simulations: int = 10_000,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the authoritative FAIR Monte Carlo risk pipeline for a dataset version.
        Outputs are saved strictly under outputs/{org_id}/{dataset_id}/{run_id}/
        Results are persisted to the database and alerts/regulatory assessments are triggered.

        When ``run_id`` is supplied, the pre-created queued run is reused so the API
        can return the run identifier in the 202 response.
        """
        dataset = self.db.scalars(
            select(Dataset).where(Dataset.id == dataset_id, Dataset.organization_id == org_id)
        ).first()
        if not dataset:
            raise ResourceNotFoundError(message="Dataset not found")

        version_id = dataset.active_version_id
        if not version_id:
            version = self.db.scalars(
                select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.version_number.desc())
            ).first()
            if not version:
                raise BadInputError(message="Dataset has no versions to run")
            version_id = version.id

        now = datetime.now(timezone.utc)
        run: Optional[RiskRun] = None
        if run_id:
            run = self.db.scalars(
                select(RiskRun).where(
                    RiskRun.id == run_id,
                    RiskRun.organization_id == org_id,
                    RiskRun.dataset_id == dataset.id,
                )
            ).first()

        if run is None:
            run = RiskRun(
                organization_id=org_id,
                dataset_id=dataset.id,
                dataset_version_id=version_id,
                config_version="1.0.0",
                model_version="fair-v2.1",
                code_version="1.0.0",
                rng_seed=rng_seed,
                state="running",
                started_at=now,
                created_at=now,
            )
            self.db.add(run)
            self.db.commit()
            self.db.refresh(run)
        else:
            run.state = "running"
            run.started_at = now
            run.rng_seed = rng_seed
            self.db.commit()

        # Resolve paths. Only tenant-scoped storage is authoritative; the built-in
        # sample bundle is used solely for datasets explicitly flagged as demo.
        data_dir = settings.DATA_BASE_DIR / "tenants" / org_id / dataset.id / version_id
        if not data_dir.exists():
            if dataset.dataset_type == "demo":
                # Built-in sample bundle shipped with the product (not tenant data).
                data_dir = settings.DATA_BASE_DIR
                logger.warning(
                    "Demo dataset %s has no materialized version files; using built-in sample bundle",
                    dataset.id,
                )
            else:
                run.state = "failed"
                run.safe_error_code = "SOURCE_DATA_MISSING"
                self.db.commit()
                raise BadInputError(
                    message="Source dataset files for this version are unavailable"
                )

        out_dir = self.get_run_output_dir(org_id, dataset.id, run.id)
        run.artifact_base_path = str(out_dir.relative_to(settings.OUTPUT_BASE_DIR))

        try:
            # 1. Enrich CVEs with Threat Intelligence
            threat_intel = ThreatIntelService(self.db)
            vuln_findings = self.db.query(VulnerabilityFinding).filter(
                VulnerabilityFinding.dataset_version_id == version_id
            ).all()
            cve_list = [f.cve_id for f in vuln_findings if f.cve_id]
            enriched = threat_intel.enrich_cves(cve_list)
            run.threat_intel_snapshot_refs = {cve: meta["snapshot_id"] for cve, meta in enriched.items()}

            # 2. Run Engine Pipeline
            config = EngineConfig(
                data_dir=data_dir,
                output_dir=out_dir,
                n_simulations=n_simulations,
                random_seed=rng_seed,
            )
            pipeline = RiskPipeline(config=config)
            pipeline.run_all()

            # 3. Read outputs and persist summary records to database
            asset_summary_df = pd.read_parquet(out_dir / "asset_risk_summary.parquet")
            org_summary_df = pd.read_parquet(out_dir / "org_risk_summary.parquet")
            scenarios_df = pd.read_parquet(out_dir / "control_scenario_results.parquet")

            org_row = org_summary_df.iloc[0].to_dict() if not org_summary_df.empty else {}

            # Save PortfolioRiskResult
            # The organisation summary does not carry a realised portfolio maximum
            # loss sample, so no MPL figure is reported rather than inventing a
            # multiplier on VaR99.
            max_probable_loss = None
            if "max_probable_loss_usd" in org_summary_df.columns:
                try:
                    max_probable_loss = float(org_row.get("max_probable_loss_usd"))
                except (TypeError, ValueError):
                    max_probable_loss = None

            portfolio_res = PortfolioRiskResult(
                run_id=run.id,
                artifact_key=str((out_dir / "org_risk_summary.parquet").relative_to(settings.OUTPUT_BASE_DIR)),
                total_eal_usd=float(org_row.get("total_EAL_usd", 0.0)),
                total_var95_usd=float(org_row.get("total_VaR95_usd", 0.0)),
                total_var99_usd=float(org_row.get("total_VaR99_usd", 0.0)),
                total_cvar95_usd=float(org_row.get("total_CVaR95_usd", 0.0)),
                max_probable_loss_usd=max_probable_loss,
                dependence_assumptions={"model": "element_wise_portfolio_sum", "assumption": "common_iteration_simulation"},
                currency="USD",
                summary_metrics=org_row,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(portfolio_res)

            # Save AssetRiskResults
            assets_in_version = self.db.query(Asset).filter(Asset.dataset_version_id == version_id).all()
            asset_db_map = {a.asset_key: a for a in assets_in_version}

            for _, row in asset_summary_df.iterrows():
                akey = str(row["asset_id"])
                matched_a = asset_db_map.get(akey)
                if matched_a:
                    arr = AssetRiskResult(
                        run_id=run.id,
                        asset_id=matched_a.id,
                        asset_key=akey,
                        eal_usd=float(row.get("EAL_usd", 0.0)),
                        var95_usd=float(row.get("VaR95_usd", 0.0)),
                        var99_usd=float(row.get("VaR99_usd", 0.0)),
                        cvar95_usd=float(row.get("CVaR95_usd", 0.0)),
                        primary_loss_usd=float(row.get("LM_downtime_usd", 0.0) + row.get("LM_ir_usd", 0.0)),
                        secondary_loss_usd=float(row.get("LM_data_breach_usd", 0.0) + row.get("LM_regulatory_usd", 0.0)),
                        sample_count=n_simulations,
                        confidence_status="high",
                        created_at=datetime.now(timezone.utc),
                    )
                    self.db.add(arr)

            # Save ControlScenario results
            ctrls_db = {c.catalog_id: c for c in self.db.query(SecurityControl).all()}
            for _, row in scenarios_df.iterrows():
                akey = str(row["asset_id"])
                cid = str(row["control_id"])
                matched_a = asset_db_map.get(akey)
                matched_c = ctrls_db.get(cid)
                if matched_a and matched_c:
                    cs = ControlScenario(
                        run_id=run.id,
                        asset_id=matched_a.id,
                        control_id=matched_c.id,
                        control_name=str(row.get("control_name", matched_c.name)),
                        cost_usd=float(row.get("cost_usd", 0.0)),
                        eal_before_usd=float(row.get("EAL_before", 0.0)),
                        eal_after_usd=float(row.get("EAL_after", 0.0)),
                        risk_reduction_usd=float(row.get("Risk_Reduction_usd", 0.0)),
                        rosi=float(row.get("ROSI", 0.0)),
                        created_at=datetime.now(timezone.utc),
                    )
                    self.db.add(cs)

            # 4. Trigger Regulatory Assessment
            reg_engine = RegulatoryAssessmentEngine(self.db)
            reg_engine.evaluate_dataset(dataset.id, version_id, run_id=run.id)

            # 5. Trigger Policy Alerts
            alert_service = AlertService(self.db)
            alert_service.evaluate_risk_run_alerts(run.id, org_id, dataset.id)

            run.state = "completed"
            run.finished_at = datetime.now(timezone.utc)

            # Data-quality and uncertainty labels surfaced on every risk response.
            unmatched_findings = self.db.query(VulnerabilityFinding).filter(
                VulnerabilityFinding.dataset_version_id == version_id,
                VulnerabilityFinding.match_status != "matched",
            ).count()
            version_row = self.db.scalars(
                select(DatasetVersion).where(DatasetVersion.id == version_id)
            ).first()
            intel_unavailable = sum(
                1 for meta in enriched.values()
                if meta.get("status") not in ("fresh", "cached", "stale")
            )
            if unmatched_findings == 0 and intel_unavailable == 0:
                data_quality = "validated_inputs"
            elif version_row is not None and not version_row.is_valid:
                data_quality = "failed_validation"
            else:
                data_quality = "partial_input_coverage"

            run.summary_metrics = {
                "total_eal_usd": portfolio_res.total_eal_usd,
                "total_var95_usd": portfolio_res.total_var95_usd,
                "total_cvar95_usd": portfolio_res.total_cvar95_usd,
                "total_assets_modeled": len(asset_summary_df),
                "data_quality": data_quality,
                "uncertainty": "monte_carlo_p50_p95_p99_quantiles",
                "unmatched_findings": int(unmatched_findings),
                "threat_intel_sources_unavailable": int(intel_unavailable),
                "assumptions": [
                    "FAIR-aligned Monte Carlo; per-iteration asset losses aggregated into a portfolio distribution.",
                    "Asset losses treated as independent unless a documented dependence model is applied.",
                    "Quantiles (VaR95/VaR99/CVaR) are simulation estimates, not guaranteed loss bounds.",
                ],
            }
            self.db.commit()

            return {
                "run_id": run.id,
                "status": "completed",
                "summary": run.summary_metrics,
                "artifact_path": run.artifact_base_path,
            }

        except Exception as e:
            logger.exception("Risk run %s failed", run.id)
            run.state = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.safe_error_code = type(e).__name__
            self.db.commit()
            raise
