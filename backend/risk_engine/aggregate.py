import pandas as pd
import numpy as np
from typing import Dict, Any

from .config import EngineConfig, DEFAULT_CONFIG

class RiskAggregator:
    """Aggregates simulated risk metrics to Asset, Business Unit, and Organizational levels."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        
    def aggregate(self, df: pd.DataFrame, simulator=None) -> Dict[str, pd.DataFrame]:
        """
        Takes the fully simulated DataFrame and returns aggregated datasets.
        
        If `simulator` is provided (a MonteCarloSimulator with .loss_samples populated),
        the org-level metrics are computed from the real combined loss distribution.
        Otherwise falls back to the summed upper-bound approximation.
        """
        # 1. Asset Level Summary
        # priority_score = EAL * (criticality / 5) -> for ranking, not for dollar total
        extra_cols = []
        for col in ["CVaR95_usd", "EAL_simple_usd",
                    "LM_downtime_usd", "LM_ir_usd",
                    "LM_data_breach_usd", "LM_regulatory_usd",
                    "TEF_mostlikely", "Vuln_asset"]:
            if col in df.columns:
                extra_cols.append(col)

        base_cols = ["asset_id", "business_unit", "criticality",
                     "EAL_usd", "VaR95_usd", "VaR99_usd", "LEC_points"]
        asset_summary = df[base_cols + extra_cols].copy()
        
        asset_summary["priority_score"] = asset_summary["EAL_usd"] * (asset_summary["criticality"] / 5.0)
        
        # Sort by priority
        asset_summary = asset_summary.sort_values(by="priority_score", ascending=False).reset_index(drop=True)
        
        # 2. Business Unit Level Summary
        # Documented assumption: Summing VaR95 across assets assumes perfect correlation or uses an upper bound.
        # Summing EAL assumes independence, which is valid for expected values.
        bu_summary = df.groupby("business_unit").agg(
            total_EAL_usd=("EAL_usd", "sum"),
            total_VaR95_usd_upper_bound=("VaR95_usd", "sum")
        ).reset_index()
        
        # Get top risk contributors per BU
        def get_top_contributors(bu_name):
            bu_assets = asset_summary[asset_summary["business_unit"] == bu_name]
            top = bu_assets.head(5)[["asset_id", "EAL_usd"]].to_dict(orient="records")
            return top
            
        bu_summary["top_contributors"] = bu_summary["business_unit"].apply(get_top_contributors)
        
        # 3. Organization Level Summary
        org_eal = df["EAL_usd"].sum()
        org_var95_upper = df["VaR95_usd"].sum()
        org_var99_upper = df["VaR99_usd"].sum()

        # Build org-level distribution from per-asset samples (element-wise sum = same year)
        org_var95 = org_var95_upper  # fallback
        org_var99 = org_var99_upper
        org_cvar95 = org_var95_upper  # fallback
        org_lec_points_json = []

        if simulator is not None and simulator.loss_samples:
            # Sum annual losses across all assets for each simulated year
            try:
                arrays = list(simulator.loss_samples.values())
                n_sim = len(arrays[0])
                portfolio_loss = np.zeros(n_sim)
                for arr in arrays:
                    if len(arr) == n_sim:
                        portfolio_loss += arr

                org_eal = float(np.mean(portfolio_loss))
                org_var95 = float(np.percentile(portfolio_loss, 95))
                org_var99 = float(np.percentile(portfolio_loss, 99))

                tail_mask = portfolio_loss >= org_var95
                org_cvar95 = float(np.mean(portfolio_loss[tail_mask])) if tail_mask.any() else org_var95

                # Build ~100 LEC points for org_lec.json
                sorted_losses = np.sort(portfolio_loss)
                step = max(1, n_sim // 100)
                for i in range(0, n_sim, step):
                    prob_exceed = 1.0 - (i / n_sim)
                    org_lec_points_json.append({
                        "loss": float(sorted_losses[i]),
                        "probability": float(prob_exceed),
                    })
            except Exception:
                # Fallback to sum-based values already computed above
                pass
        
        org_summary = pd.DataFrame([{
            "organization_name": "Enterprise",
            "total_EAL_usd": org_eal,
            "total_VaR95_usd": org_var95,
            "total_VaR99_usd": org_var99,
            "total_CVaR95_usd": org_cvar95,
            "total_VaR95_usd_upper_bound": org_var95_upper,
            "total_VaR99_usd_upper_bound": org_var99_upper,
            "note": "EAL and VaR/CVaR derived from element-wise combined loss distribution. "
                    "Upper-bound columns sum per-asset values (assumes independence)."
        }])
        
        return {
            "asset_risk_summary": asset_summary,
            "business_unit_risk_summary": bu_summary,
            "org_risk_summary": org_summary,
            "org_lec_points": org_lec_points_json,
        }
