import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from risk_engine.investment_optimizer import optimize_investments
from risk_engine.frontier import compute_frontier
from risk_engine.framework_mapper import get_compliance_posture, get_compliance_gaps
from api.chat import router as chat_router
from api.upload import router as upload_router
from api.live_feed import router as live_feed_router

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Cyber Risk Quantification API",
    description="API for accessing computed financial cyber risk metrics.",
    version="1.0.0",
)

app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(live_feed_router)

# --- CORS: required so the frontend dashboard (running on a different
# port, e.g. localhost:3000 or localhost:5173) can call this API.
# For the hackathon demo, allow_origins=["*"] is simplest. If you want to
# be stricter, replace "*" with your actual frontend dev server URL(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory relative to this file
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def load_parquet(filename: str) -> pd.DataFrame:
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Output file not found: {file_path}. Have you run `python -m risk_engine.pipeline`?"
        )
    return pd.read_parquet(file_path)


def _handle_load_error(e: Exception):
    """Distinguish 'pipeline not run yet' from real server errors."""
    if isinstance(e, FileNotFoundError):
        raise HTTPException(status_code=503, detail=str(e))
    logger.exception("Unexpected error while serving request")
    raise HTTPException(status_code=500, detail=str(e))


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health_check():
    """Returns the API status."""
    return {"status": "ok"}


@app.get("/risk/assets")
def get_asset_risk_summary():
    """Returns risk metrics for all assets."""
    try:
        df = load_parquet("asset_risk_summary.parquet")
        cols = ["asset_id", "business_unit", "criticality", "EAL_usd", "VaR95_usd", "VaR99_usd", "priority_score"]
        # Include CVaR95 if present
        if "CVaR95_usd" in df.columns:
            cols.append("CVaR95_usd")
        summary_df = df[cols]
        return summary_df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/risk/assets/{asset_id}")
def get_asset_risk_detail(asset_id: str):
    """Returns detailed risk metrics for a single asset, including the Loss Exceedance Curve (if present)."""
    try:
        df = load_parquet("asset_risk_summary.parquet")
        asset_data = df[df["asset_id"] == asset_id]
        if asset_data.empty:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

        record = asset_data.iloc[0].to_dict()

        # Defensively convert any numpy/array-like fields to plain lists so
        # they serialize cleanly to JSON for the frontend.
        for key, value in record.items():
            if isinstance(value, np.ndarray):
                record[key] = value.tolist()
            elif isinstance(value, (np.integer,)):
                record[key] = int(value)
            elif isinstance(value, (np.floating,)):
                record[key] = float(value)

        return record
    except HTTPException:
        raise
    except Exception as e:
        _handle_load_error(e)


@app.get("/risk/assets/{asset_id}/drivers")
def get_asset_drivers(asset_id: str):
    """
    Returns top EAL drivers for a single asset (counterfactual analysis).
    Each driver shows how much EAL would change if one factor were neutralised.
    """
    try:
        df = load_parquet("asset_risk_summary.parquet")
        asset_data = df[df["asset_id"] == asset_id]
        if asset_data.empty:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")

        asset_row = asset_data.iloc[0]

        from risk_engine.drivers import explain_asset
        from risk_engine.config import DEFAULT_CONFIG

        drivers = explain_asset(asset_row, df, DEFAULT_CONFIG)
        return {
            "asset_id": asset_id,
            "eal_simple_usd": float(asset_row.get("EAL_simple_usd", 0.0)),
            "drivers": drivers,
        }
    except HTTPException:
        raise
    except Exception as e:
        _handle_load_error(e)


@app.get("/risk/business-units")
def get_business_unit_risk():
    """Returns aggregated risk metrics per Business Unit."""
    try:
        df = load_parquet("business_unit_risk_summary.parquet")
        return df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/risk/organization")
def get_organization_risk():
    """Returns top-level enterprise risk metrics, including CVaR95."""
    try:
        df = load_parquet("org_risk_summary.parquet")
        return df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/controls/scenarios")
def get_all_scenarios():
    """Returns all control what-if scenarios."""
    try:
        df = load_parquet("control_scenario_results.parquet")
        return df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/controls/roi")
def get_controls_roi():
    """Returns controls ranked by overall Return on Security Investment (ROSI).
    
    ROSI = (Risk_Reduction_usd − cost_usd) / cost_usd  (standard formula)
    """
    try:
        df = load_parquet("control_scenario_results.parquet")
        grouped = df.groupby(["control_id", "control_name"]).agg(
            total_cost_usd=("cost_usd", "sum"),
            total_risk_reduction_usd=("Risk_Reduction_usd", "sum"),
            applicable_assets=("asset_id", "count"),
        ).reset_index()

        # Standard ROSI: (Risk_Reduction − Cost) / Cost
        grouped["overall_ROSI"] = (
            (grouped["total_risk_reduction_usd"] - grouped["total_cost_usd"])
            / grouped["total_cost_usd"]
        )
        grouped = grouped.sort_values(by="overall_ROSI", ascending=False)
        return grouped.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/controls/optimize")
def get_optimal_investment_plan(
    budget: float = Query(..., gt=0, description="Available security budget in USD"),
    one_control_per_asset: bool = Query(
        True, description="Restrict to at most one control per asset (recommended default)"
    ),
):
    """
    Runs the budget-constrained investment optimizer and returns the
    recommended set of (asset, control) actions for the given budget,
    along with a comparison against a naive greedy-by-ROSI baseline.

    This is the endpoint the dashboard's "what-if budget" slider should call.
    """
    try:
        scenarios = load_parquet("control_scenario_results.parquet")
        result = optimize_investments(scenarios, budget_usd=budget, one_control_per_asset=one_control_per_asset)

        return {
            "budget_usd": budget,
            "total_cost_usd": result["total_cost_usd"],
            "total_risk_reduction_usd": result["total_risk_reduction_usd"],
            "budget_utilization_pct": result["budget_utilization_pct"],
            "n_actions_selected": result["n_actions_selected"],
            "residual_eal_usd": result["residual_eal_usd"],
            "greedy_comparison": result["greedy_comparison"],
            "selected_actions": result["selected"].to_dict(orient="records"),
        }
    except Exception as e:
        _handle_load_error(e)


# ---------------------------------------------------------------------------
# Compliance Framework Mapping Endpoints
# ---------------------------------------------------------------------------

@app.get("/compliance/posture")
def get_compliance_posture_endpoint():
    """Returns compliance coverage posture across all mapped frameworks."""
    try:
        # Get deployed control IDs from asset_controls in the ingested data
        data_dir = Path(__file__).resolve().parent.parent / "data"
        asset_controls_path = data_dir / "asset_controls.csv"

        deployed_ids = set()
        if asset_controls_path.exists():
            ac_df = pd.read_csv(asset_controls_path)
            if "control_id" in ac_df.columns:
                deployed_ids = set(ac_df["control_id"].unique())

        posture = get_compliance_posture(deployed_ids)
        return posture
    except Exception as e:
        logger.exception("Error computing compliance posture")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compliance/gaps")
def get_compliance_gaps_endpoint():
    """Returns compliance gaps — framework requirements not covered by deployed controls."""
    try:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        asset_controls_path = data_dir / "asset_controls.csv"

        deployed_ids = set()
        if asset_controls_path.exists():
            ac_df = pd.read_csv(asset_controls_path)
            if "control_id" in ac_df.columns:
                deployed_ids = set(ac_df["control_id"].unique())

        gaps = get_compliance_gaps(deployed_ids)
        return gaps
    except Exception as e:
        logger.exception("Error computing compliance gaps")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Investment Efficient Frontier Endpoint
# ---------------------------------------------------------------------------

_frontier_cache = None

@app.get("/controls/frontier")
def get_investment_frontier():
    """Returns the efficient frontier data — optimizer results at multiple budget levels (cached)."""
    global _frontier_cache
    if _frontier_cache is not None:
        return _frontier_cache

    cache_file = OUTPUT_DIR / "frontier_cache.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                _frontier_cache = json.load(f)
            return _frontier_cache
        except Exception as e:
            logger.warning(f"Error reading frontier cache: {e}")

    try:
        scenarios = load_parquet("control_scenario_results.parquet")
        frontier = compute_frontier(scenarios)
        _frontier_cache = frontier
        try:
            with open(cache_file, "w") as f:
                json.dump(frontier, f)
        except Exception:
            pass
        return frontier
    except Exception as e:
        _handle_load_error(e)


# ---------------------------------------------------------------------------
# Risk Trend Endpoint
# ---------------------------------------------------------------------------

@app.get("/risk/trend")
def get_risk_trend():
    """Returns historical risk trend data for visualization."""
    try:
        df = load_parquet("risk_trend.parquet")
        return df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


# ---------------------------------------------------------------------------
# ML Predictions Endpoint
# ---------------------------------------------------------------------------

@app.get("/predictions/vulnerabilities")
def get_vuln_predictions():
    """Returns ML vulnerability exploitation predictions."""
    try:
        df = load_parquet("vuln_predictions.parquet")
        return df.to_dict(orient="records")
    except Exception as e:
        _handle_load_error(e)


@app.get("/predictions/threat-forecast")
def get_threat_forecast(horizon_days: int = 14):
    """
    Returns sequential time neural network (LSTM) Threat Event Frequency (TEF) forecasts,
    forward attack surge trajectories, and MITRE ATT&CK technique transition probabilities.
    """
    forecast_file = OUTPUT_DIR / "threat_forecast.json"
    
    # If cached file exists, return it
    if forecast_file.exists():
        try:
            with open(forecast_file, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.warning(f"Error reading cached threat_forecast.json: {e}")

    # Otherwise compute on-the-fly from threat_events data
    try:
        from risk_engine.threat_forecaster import ThreatSequenceForecaster
        data_dir = Path(__file__).resolve().parent.parent / "data"
        threat_events_path = data_dir / "threat_events.csv"
        
        if not threat_events_path.exists():
            raise HTTPException(status_code=404, detail="Threat events telemetry not found.")
            
        df = pd.read_csv(threat_events_path)
        forecaster = ThreatSequenceForecaster(window_size=7, forecast_horizon=horizon_days)
        result = forecaster.train_and_forecast(df)
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(forecast_file, "w") as f:
            json.dump(result, f, indent=2)
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error computing LSTM threat forecast")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Asset Dependency & Systemic Risk (Active Directory Graph) Endpoints
# ---------------------------------------------------------------------------

_graph_engine = None

def _get_graph_engine():
    global _graph_engine
    if _graph_engine is None:
        from risk_engine.dependency_graph import DependencyGraphEngine
        _graph_engine = DependencyGraphEngine()
        _graph_engine.build_graph()
    return _graph_engine


@app.get("/risk/dependency-graph")
def get_dependency_graph():
    """Returns the Active Directory trust & lateral movement dependency graph."""
    try:
        engine = _get_graph_engine()
        return engine.build_graph()
    except Exception as e:
        logger.exception("Error building dependency graph")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/risk/dependency-graph/propagate")
def get_risk_propagation(
    breached_asset_id: str = Query(..., description="Initial breached asset ID, e.g. AST-1000")
):
    """
    Computes lateral movement compromise probabilities and cascading financial
    loss exposure across the dependency graph starting from breached_asset_id.
    """
    try:
        engine = _get_graph_engine()
        return engine.propagate_risk(breached_asset_id)
    except Exception as e:
        logger.exception("Error calculating risk propagation")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Portfolio-Wide Loss Exceedance Curve (LEC) Endpoint
# ---------------------------------------------------------------------------

@app.get("/risk/portfolio-lec")
def get_portfolio_lec():
    """
    Returns enterprise-wide aggregate Loss Exceedance Curve (LEC) combining
    tail-risk loss distributions across all assets.
    LEC points are derived from the real combined loss distribution saved by
    the pipeline in org_lec.json.  Falls back to asset-level sums when that
    file is unavailable.
    """
    try:
        df = load_parquet("asset_risk_summary.parquet")
        org_df = load_parquet("org_risk_summary.parquet")
        org = org_df.iloc[0].to_dict() if not org_df.empty else {}

        total_eal = float(org.get("total_EAL_usd", df["EAL_usd"].sum()))
        total_var95 = float(org.get("total_VaR95_usd", df["VaR95_usd"].sum()))
        total_var99 = float(org.get("total_VaR99_usd", df["VaR99_usd"].sum()))
        total_cvar95 = float(org.get("total_CVaR95_usd", total_var95))

        # Try to load real LEC points from org_lec.json
        org_lec_file = OUTPUT_DIR / "org_lec.json"
        if org_lec_file.exists():
            try:
                with open(org_lec_file, "r") as f:
                    raw_points = json.load(f)
                # Convert to the chart format expected by the frontend
                lec_points = []
                for pt in raw_points:
                    prob_pct = pt["probability"] * 100
                    label = f"{prob_pct:.1f}%"
                    lec_points.append({
                        "probability": label,
                        "prob_num": round(prob_pct, 2),
                        "loss_usd": round(pt["loss"], 2),
                    })
            except Exception as e:
                logger.warning(f"Could not read org_lec.json: {e}")
                lec_points = _build_fallback_lec(total_eal, total_var95, total_var99)
        else:
            lec_points = _build_fallback_lec(total_eal, total_var95, total_var99)

        max_loss = lec_points[-1]["loss_usd"] if lec_points else round(total_var99 * 1.45, 2)

        return {
            "organization_name": "Enterprise Portfolio",
            "total_eal_usd": total_eal,
            "total_var95_usd": total_var95,
            "total_var99_usd": total_var99,
            "total_cvar95_usd": total_cvar95,
            "max_probable_loss_usd": max_loss,
            "total_assets_modeled": len(df),
            "lec_points": lec_points,
        }
    except Exception as e:
        _handle_load_error(e)


def _build_fallback_lec(total_eal: float, total_var95: float, total_var99: float) -> list:
    """Fallback LEC when org_lec.json is not available."""
    return [
        {"probability": "50%", "prob_num": 50, "loss_usd": round(total_eal * 0.72, 2)},
        {"probability": "30%", "prob_num": 30, "loss_usd": round(total_eal * 0.95, 2)},
        {"probability": "20%", "prob_num": 20, "loss_usd": round(total_eal * 1.25, 2)},
        {"probability": "10%", "prob_num": 10, "loss_usd": round(total_eal * 1.80, 2)},
        {"probability": "5% (VaR 95)", "prob_num": 5, "loss_usd": round(total_var95, 2)},
        {"probability": "2%", "prob_num": 2, "loss_usd": round(total_var95 * 1.22, 2)},
        {"probability": "1% (VaR 99)", "prob_num": 1, "loss_usd": round(total_var99, 2)},
        {"probability": "0.1% (Extreme)", "prob_num": 0.1, "loss_usd": round(total_var99 * 1.45, 2)},
    ]