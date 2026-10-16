import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from .config import EngineConfig, DEFAULT_CONFIG
from .likelihood import LikelihoodModel
from .frequency import FrequencyModel
from .loss_magnitude import LossMagnitudeModel
from .simulate import MonteCarloSimulator

def generate_risk_trend(base_df: pd.DataFrame, raw_data: dict, config: EngineConfig = DEFAULT_CONFIG, n_months: int = 6) -> pd.DataFrame:
    """Generate synthetic historical risk snapshots for trend visualization.
    
    Creates past 'monthly' snapshots by perturbing the current state:
    - Older months had fewer controls deployed (controls added over time)
    - Older months had slightly different vulnerability profiles
    - This creates a realistic narrative of risk decreasing as security matures
    """
    snapshots = []
    now = datetime.now()
    
    # Current state metrics from the already-computed base_df
    current_eal = float(base_df["total_EAL_usd"].sum())
    current_var95 = float(base_df["total_VaR95_usd_upper_bound"].sum())
    current_n_controls = int(raw_data.get("asset_controls", pd.DataFrame()).shape[0] 
                            if isinstance(raw_data.get("asset_controls"), pd.DataFrame) 
                            else len(raw_data.get("asset_controls", [])))
    current_n_vulns = int(raw_data.get("vulnerabilities", pd.DataFrame()).shape[0]
                         if isinstance(raw_data.get("vulnerabilities"), pd.DataFrame)
                         else len(raw_data.get("vulnerabilities", [])))
    
    rng = np.random.default_rng(config.random_seed + 999)
    
    for month_offset in range(n_months, 0, -1):
        # Simulate degraded security posture in the past
        # Fewer controls deployed, more open vulnerabilities
        control_factor = 1.0 + (month_offset * 0.08)  # 8% more risk per month back
        vuln_factor = 1.0 + (month_offset * 0.05)      # 5% more vulns per month back
        noise = rng.normal(1.0, 0.03)                   # ±3% random noise
        
        past_eal = current_eal * control_factor * noise
        past_var95 = current_var95 * control_factor * noise
        past_controls = max(0, int(current_n_controls * (1.0 - month_offset * 0.12)))
        past_vulns = int(current_n_vulns * vuln_factor * rng.normal(1.0, 0.05))
        
        snapshot_date = now - timedelta(days=30 * month_offset)
        snapshots.append({
            "date": snapshot_date.strftime("%Y-%m-%d"),
            "label": f"{month_offset}mo ago",
            "month_offset": -month_offset,
            "total_EAL_usd": round(past_eal, 2),
            "total_VaR95_usd": round(past_var95, 2),
            "n_controls_deployed": past_controls,
            "n_open_vulns": past_vulns,
            "risk_delta_pct": round((past_eal / current_eal - 1) * 100, 1),
        })
    
    # Add current snapshot
    snapshots.append({
        "date": now.strftime("%Y-%m-%d"),
        "label": "Current",
        "month_offset": 0,
        "total_EAL_usd": round(current_eal, 2),
        "total_VaR95_usd": round(current_var95, 2),
        "n_controls_deployed": current_n_controls,
        "n_open_vulns": current_n_vulns,
        "risk_delta_pct": 0.0,
    })
    
    return pd.DataFrame(snapshots)
