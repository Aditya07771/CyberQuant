import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_org, require_dataset_access, require_run_access
from core.errors import BadInputError, ResourceNotFoundError
from db.models import Dataset, Organization, RiskRun
from db.session import get_db
from risk_engine.drivers import explain_asset
from risk_engine.framework_mapper import get_compliance_gaps, get_compliance_posture
from risk_engine.frontier import compute_frontier
from risk_engine.investment_optimizer import optimize_investments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/datasets/{dataset_id}/runs/{run_id}", tags=["risk"])


def _run_output_dir(run: RiskRun) -> Path:
    if run.artifact_base_path:
        candidate = Path(run.artifact_base_path)
        if candidate.is_absolute():
            return candidate
        return settings.OUTPUT_BASE_DIR / candidate
    return settings.OUTPUT_BASE_DIR / run.organization_id / run.dataset_id / run.id


def _load_run_parquet(run: RiskRun, filename: str) -> pd.DataFrame:
    """Loads a parquet artifact strictly from the tenant's authorized run directory."""
    file_path = _run_output_dir(run) / filename
    if not file_path.exists():
        raise ResourceNotFoundError(message=f"Artifact '{filename}' not found for run '{run.id}'")
    return pd.read_parquet(file_path)


def _load_run_json(run: RiskRun, filename: str) -> Any:
    """Loads a JSON artifact strictly from the tenant's authorized run directory."""
    file_path = _run_output_dir(run) / filename
    if not file_path.exists():
        raise ResourceNotFoundError(message=f"Artifact '{filename}' not found for run '{run.id}'")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


MODEL_ASSUMPTIONS = [
    "FAIR-aligned Monte Carlo loss model; per-iteration asset losses aggregated into a portfolio distribution.",
    "Asset losses are treated as independent unless a documented common-event/dependence model is applied.",
    "Threat and loss-magnitude inputs are derived from the selected dataset version; stale or missing inputs are flagged rather than zeroed.",
]


def build_run_metadata(run: RiskRun, dataset: Optional[Dataset] = None, version: Optional[Any] = None) -> Dict[str, Any]:
    """
    Canonical per-run metadata envelope required on every risk response:
    currency, run_id, model/config/input versions, calculation time, data quality,
    uncertainty and assumption/source references.
    """
    version_obj = version or getattr(run, "version", None)
    summary = run.summary_metrics or {}
    data_quality = summary.get("data_quality") or summary.get("data_sufficiency") or "reported"
    uncertainty = summary.get("uncertainty") or "monte_carlo_quantiles"
    return {
        "run_id": run.id,
        "dataset_id": run.dataset_id,
        "dataset_version_id": run.dataset_version_id,
        "currency": getattr(version_obj, "currency", None) or "USD",
        "model_version": run.model_version,
        "config_version": run.config_version,
        "code_version": run.code_version,
        "input_version": run.input_hash,
        "rng_seed": run.rng_seed,
        "calculated_at": (run.finished_at or run.created_at).isoformat() if (run.finished_at or run.created_at) else None,
        "state": run.state,
        "data_quality": data_quality,
        "uncertainty": uncertainty,
        "assumptions": summary.get("assumptions") or MODEL_ASSUMPTIONS,
        "threat_intel_snapshot_refs": run.threat_intel_snapshot_refs,
    }


def collection_envelope(rows: List[Any], run: RiskRun, **extra: Any) -> Dict[str, Any]:
    payload = {"run": build_run_metadata(run), "results": rows}
    payload.update(extra)
    return payload


def object_envelope(data: Any, run: RiskRun, **extra: Any) -> Dict[str, Any]:
    payload = {"run": build_run_metadata(run), "data": data}
    payload.update(extra)
    return payload


@router.get("/risk/assets")
def get_run_assets_summary(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "asset_risk_summary.parquet")
    cols = ["asset_id", "business_unit", "criticality", "EAL_usd", "VaR95_usd", "VaR99_usd", "priority_score"]
    if "CVaR95_usd" in df.columns:
        cols.append("CVaR95_usd")
    cols = [c for c in cols if c in df.columns]
    return collection_envelope(df[cols].to_dict(orient="records"), run)


@router.get("/risk/assets/{asset_id}")
def get_run_asset_detail(
    dataset_id: str,
    run_id: str,
    asset_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "asset_risk_summary.parquet")
    row = df[df["asset_id"] == asset_id]
    if row.empty:
        raise ResourceNotFoundError(message=f"Asset '{asset_id}' not found in run results")

    record = row.iloc[0].to_dict()
    for k, v in record.items():
        if isinstance(v, np.ndarray):
            record[k] = v.tolist()
        elif isinstance(v, (np.integer,)):
            record[k] = int(v)
        elif isinstance(v, (np.floating,)):
            record[k] = float(v)
    return object_envelope(record, run)


@router.get("/risk/assets/{asset_id}/drivers")
def get_run_asset_drivers(
    dataset_id: str,
    run_id: str,
    asset_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "asset_risk_summary.parquet")
    row = df[df["asset_id"] == asset_id]
    if row.empty:
        raise ResourceNotFoundError(message=f"Asset '{asset_id}' not found")

    from risk_engine.config import DEFAULT_CONFIG
    drivers = explain_asset(row.iloc[0], df, DEFAULT_CONFIG)
    return object_envelope({
        "asset_id": asset_id,
        "run_id": run.id,
        "eal_simple_usd": float(row.iloc[0].get("EAL_simple_usd", 0.0)),
        "drivers": drivers,
    }, run)


@router.get("/risk/business-units")
def get_run_bu_summary(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "business_unit_risk_summary.parquet")
    return collection_envelope(df.to_dict(orient="records"), run)


@router.get("/risk/organization")
def get_run_org_summary(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "org_risk_summary.parquet")
    rows = df.to_dict(orient="records")
    row = rows[0] if rows else None
    return object_envelope(row, run)


@router.get("/risk/portfolio-lec")
def get_run_portfolio_lec(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "asset_risk_summary.parquet")
    org_df = _load_run_parquet(run, "org_risk_summary.parquet")
    org = org_df.iloc[0].to_dict() if not org_df.empty else {}

    total_eal = float(org.get("total_EAL_usd", df["EAL_usd"].sum()))
    total_var95 = float(org.get("total_VaR95_usd", df["VaR95_usd"].sum()))
    total_var99 = float(org.get("total_VaR99_usd", df["VaR99_usd"].sum()))
    total_cvar95 = float(org.get("total_CVaR95_usd", total_var95))

    try:
        raw_points = _load_run_json(run, "org_lec.json")
        lec_points = []
        for pt in raw_points:
            prob_pct = pt["probability"] * 100
            lec_points.append({
                "probability": f"{prob_pct:.1f}%",
                "prob_num": round(prob_pct, 2),
                "loss_usd": round(pt["loss"], 2),
            })
        lec_source = "simulated_distribution"
    except Exception:
        lec_points = [
            {"probability": "5% (VaR 95)", "prob_num": 5, "loss_usd": round(total_var95, 2)},
            {"probability": "1% (VaR 99)", "prob_num": 1, "loss_usd": round(total_var99, 2)},
        ]
        lec_source = "var_quantile_approximation"

    return object_envelope({
        "organization_name": "Enterprise Portfolio",
        "run_id": run.id,
        "total_eal_usd": total_eal,
        "total_var95_usd": total_var95,
        "total_var99_usd": total_var99,
        "total_cvar95_usd": total_cvar95,
        "total_assets_modeled": len(df),
        "lec_points": lec_points,
        "lec_source": lec_source,
    }, run)


@router.get("/risk/trend")
def get_run_risk_trend(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "risk_trend.parquet")
    return collection_envelope(df.to_dict(orient="records"), run)


@router.get("/risk/dependency-graph")
def get_run_dependency_graph(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
    db: Session = Depends(get_db),
):
    from risk_engine.dependency_graph import DependencyGraphEngine

    assets_df = None
    risk_df = None
    try:
        risk_df = _load_run_parquet(run, "asset_risk_summary.parquet")
    except ResourceNotFoundError:
        risk_df = None

    assets_df = _load_run_assets_inventory(db, run)

    engine = DependencyGraphEngine()
    graph_data = engine.build_graph(assets_df=assets_df, risk_summary_df=risk_df, seed=run.rng_seed)
    graph_data["edge_source"] = "inferred"
    return object_envelope(graph_data, run)


def _load_run_assets_inventory(db: Session, run: RiskRun) -> Optional[pd.DataFrame]:
    """Builds the run-scoped asset inventory DataFrame from the database (never a global file)."""
    from db.models import Asset

    assets = db.scalars(select(Asset).where(Asset.dataset_version_id == run.dataset_version_id)).all()
    if not assets:
        return None
    return pd.DataFrame([
        {
            "asset_id": a.asset_key,
            "hostname": a.hostname or a.asset_key,
            "business_unit": a.business_unit,
            "criticality": a.criticality,
            "os": a.os,
            "financial_value_usd": a.financial_value_usd,
        }
        for a in assets
    ])


@router.get("/risk/dependency-graph/propagate")
def get_run_risk_propagation(
    dataset_id: str,
    run_id: str,
    breached_asset_id: str = Query(..., description="Root compromised asset key"),
    run: RiskRun = Depends(require_run_access),
    db: Session = Depends(get_db),
):
    from risk_engine.dependency_graph import DependencyGraphEngine

    risk_df = None
    try:
        risk_df = _load_run_parquet(run, "asset_risk_summary.parquet")
    except ResourceNotFoundError:
        risk_df = None

    engine = DependencyGraphEngine()
    engine.build_graph(
        assets_df=_load_run_assets_inventory(db, run),
        risk_summary_df=risk_df,
        seed=run.rng_seed,
    )
    try:
        result = engine.propagate_risk(breached_asset_id)
    except KeyError:
        raise ResourceNotFoundError(message=f"Asset '{breached_asset_id}' not found in run inventory")
    return object_envelope(result, run)


@router.get("/predictions/vulnerabilities")
def get_run_vuln_predictions(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    try:
        df = _load_run_parquet(run, "vuln_predictions.parquet")
        rows = df.to_dict(orient="records")
        return collection_envelope(
            rows,
            run,
            ml_metadata={
                "model_type": "vulnerability_exploitation_predictor",
                "model_version": run.model_version,
                "data_sufficiency": "trained_on_run_features",
                "calibration": "uncalibrated_research_output",
                "human_review_required": True,
            },
        )
    except ResourceNotFoundError:
        return collection_envelope(
            [],
            run,
            ml_metadata={
                "model_type": "vulnerability_exploitation_predictor",
                "model_version": run.model_version,
                "data_sufficiency": "insufficient_data",
                "human_review_required": True,
            },
        )


@router.get("/predictions/threat-forecast")
def get_run_threat_forecast(
    dataset_id: str,
    run_id: str,
    horizon_days: int = Query(14, ge=7, le=60),
    run: RiskRun = Depends(require_run_access),
):
    ml_meta = {
        "model_type": "threat_sequence_forecaster",
        "model_version": run.model_version,
        "calibration": "uncalibrated_research_output",
        "horizon_days": horizon_days,
        "human_review_required": True,
    }
    try:
        data = _load_run_json(run, "threat_forecast.json")
        return object_envelope(data, run, ml_metadata=ml_meta)
    except ResourceNotFoundError:
        return object_envelope(
            {
                "data_sufficiency": "insufficient_data",
                "historical_series": [],
                "forecast_series": [],
                "mitre_transitions": [],
            },
            run,
            ml_metadata={**ml_meta, "data_sufficiency": "insufficient_data"},
        )


@router.get("/controls/scenarios")
def get_run_control_scenarios(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "control_scenario_results.parquet")
    return collection_envelope(df.to_dict(orient="records"), run)


@router.get("/controls/roi")
def get_run_controls_roi(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    df = _load_run_parquet(run, "control_scenario_results.parquet")
    grouped = df.groupby(["control_id", "control_name"]).agg(
        total_cost_usd=("cost_usd", "sum"),
        total_risk_reduction_usd=("Risk_Reduction_usd", "sum"),
        applicable_assets=("asset_id", "count"),
    ).reset_index()

    # ROSI is only meaningful when cost > 0 and horizons align; null otherwise.
    grouped["_rosi_sort"] = np.where(
        grouped["total_cost_usd"] > 0,
        (grouped["total_risk_reduction_usd"] - grouped["total_cost_usd"]) / grouped["total_cost_usd"],
        np.nan,
    )
    grouped = grouped.sort_values(by="_rosi_sort", ascending=False, na_position="last")
    rows = grouped.to_dict(orient="records")
    for row in rows:
        rosi = row.pop("_rosi_sort", None)
        row["overall_ROSI"] = None if rosi is None or (isinstance(rosi, float) and np.isnan(rosi)) else float(rosi)
    return collection_envelope(rows, run)


class OptimizeRequest(BaseModel):
    budget_usd: float = Field(..., gt=0)
    one_control_per_asset: bool = True
    constraints: Optional[Dict[str, Any]] = None


@router.post("/controls/optimize")
def optimize_run_investments(
    dataset_id: str,
    run_id: str,
    payload: OptimizeRequest,
    run: RiskRun = Depends(require_run_access),
):
    scenarios = _load_run_parquet(run, "control_scenario_results.parquet")
    result = optimize_investments(
        scenarios,
        budget_usd=payload.budget_usd,
        one_control_per_asset=payload.one_control_per_asset,
    )
    return object_envelope(
        {
            "budget_usd": payload.budget_usd,
            "total_cost_usd": result["total_cost_usd"],
            "total_risk_reduction_usd": result["total_risk_reduction_usd"],
            "budget_utilization_pct": result["budget_utilization_pct"],
            "n_actions_selected": result["n_actions_selected"],
            "residual_eal_usd": result["residual_eal_usd"],
            "greedy_comparison": result["greedy_comparison"],
            "selected_actions": result["selected"].to_dict(orient="records"),
        },
        run,
        assumptions=[
            "Optimization maximises modelled marginal risk reduction within budget; it does not guarantee realised risk reduction.",
            "Control effectiveness values are model assumptions from the control catalog, not measured outcomes.",
        ],
    )


@router.get("/controls/frontier")
def get_run_investment_frontier(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
):
    try:
        return object_envelope(_load_run_json(run, "frontier_cache.json"), run)
    except ResourceNotFoundError:
        scenarios = _load_run_parquet(run, "control_scenario_results.parquet")
        return object_envelope(compute_frontier(scenarios), run)


@router.get("/compliance/posture")
def get_run_compliance_posture(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
    db: Session = Depends(get_db),
):
    # Query deployed controls from database
    from db.models import AssetControl, SecurityControl
    deployed = db.query(SecurityControl.catalog_id).join(
        AssetControl, SecurityControl.id == AssetControl.control_id
    ).filter(
        AssetControl.dataset_version_id == run.dataset_version_id,
        AssetControl.status == "active",
    ).distinct().all()

    deployed_ids = {row[0] for row in deployed}
    from risk_engine.framework_mapper import MAPPING_VERSION
    posture = get_compliance_posture(deployed_ids)
    posture["mapping_version"] = MAPPING_VERSION
    posture["source_file"] = "compliance_mappings.json"
    return object_envelope(posture, run)


@router.get("/compliance/gaps")
def get_run_compliance_gaps(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
    db: Session = Depends(get_db),
):
    from db.models import AssetControl, SecurityControl
    deployed = db.query(SecurityControl.catalog_id).join(
        AssetControl, SecurityControl.id == AssetControl.control_id
    ).filter(
        AssetControl.dataset_version_id == run.dataset_version_id,
        AssetControl.status == "active",
    ).distinct().all()

    deployed_ids = {row[0] for row in deployed}
    from risk_engine.framework_mapper import MAPPING_VERSION
    gaps = get_compliance_gaps(deployed_ids)
    return collection_envelope(gaps, run, mapping_version=MAPPING_VERSION)


@router.get("/compliance/assessments")
def get_run_regulatory_assessments(
    dataset_id: str,
    run_id: str,
    run: RiskRun = Depends(require_run_access),
    db: Session = Depends(get_db),
):
    from db.models import RegulatoryAssessment, RegulatoryRule
    assessments = db.query(RegulatoryAssessment).join(
        RegulatoryRule, RegulatoryAssessment.rule_id == RegulatoryRule.id
    ).filter(
        RegulatoryAssessment.dataset_id == dataset_id,
    ).all()

    return collection_envelope(
        [
            {
                "id": a.id,
                "rule_id": a.rule_id,
                "title": a.rule.title if a.rule else "",
                "framework_name": a.rule.framework_name if a.rule else "",
                "provision_citation": a.rule.provision_citation if a.rule else "",
                "status": a.status,
                "affected_assets_count": a.affected_assets_count,
                "potential_exposure_max_usd": a.potential_exposure_max_usd,
                "rationale": a.rationale,
                "source_url": a.rule.source_url if a.rule else "",
                "statutory_cap_disclaimer": "Statutory maximum penalty cap under verified law; actual liability requires administrative adjudication.",
            }
            for a in assessments
        ],
        run,
    )
