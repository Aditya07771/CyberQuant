import pandas as pd
import numpy as np
from typing import Dict

from .config import EngineConfig, DEFAULT_CONFIG
from .likelihood import LikelihoodModel
from .simulate import MonteCarloSimulator

class ControlScenarios:
    """Simulates 'what-if' scenarios for adding security controls to assets.
    
    NOTE: Control effectiveness is estimated via a vulnerability-ratio shortcut
    rather than full re-simulation:
        EAL_after = EAL_before × (new_vuln / old_vuln)
    This avoids re-running 20,000-iteration Monte Carlo per scenario while
    preserving directional accuracy.  ROSI uses the standard formula:
        ROSI = (Risk_Reduction_usd − cost_usd) / cost_usd
    """
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        self.likelihood = LikelihoodModel(config)
        # We can use a shared simulator instance
        self.simulator = MonteCarloSimulator(config)
        
    def evaluate_scenarios(self, base_df: pd.DataFrame, controls_df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluates adding each candidate control to each asset where it is not already deployed.
        Returns a DataFrame with scenario results including ROSI.
        
        EAL estimation method: vulnerability ratio shortcut
            EAL_after = EAL_before × (new_vuln / old_vuln)
        This avoids re-running the full Monte Carlo simulation per scenario.
        
        ROSI formula: (Risk_Reduction_usd − cost_usd) / cost_usd
        """
        results = []
        
        # We need the original risk reduction and EAL to compare against
        for _, asset_row in base_df.iterrows():
            asset_id = asset_row["asset_id"]
            active_controls = asset_row.get("active_controls", [])
            eal_before = asset_row["EAL_usd"]
            
            # If EAL is 0, no point in simulating controls (risk is already 0)
            if eal_before == 0.0:
                continue
                
            for _, control_row in controls_df.iterrows():
                control_id = control_row["control_id"]
                
                # Check if control is already deployed
                if control_id in active_controls:
                    continue
                    
                cost_usd = control_row["cost_usd"]
                risk_reduction = control_row["risk_reduction_pct"]
                
                # Create a modified row for the "after" state
                after_row = asset_row.copy()
                
                # 1. Update control resistance
                current_reduction = after_row.get("total_risk_reduction_pct", 0.0)
                
                if self.config.control_aggregation == "additive_capped":
                    new_reduction = min(1.0, current_reduction + risk_reduction)
                else:
                    # multiplicative
                    new_reduction = 1.0 - ((1.0 - current_reduction) * (1.0 - risk_reduction))
                    
                after_row["total_risk_reduction_pct"] = new_reduction
                
                # 2. Recalculate Vulnerability
                new_vuln = self.likelihood.calculate_vulnerability(after_row)
                after_row["Vuln_asset"] = new_vuln
                
                # 3. Calculate EAL after control application (vulnerability ratio shortcut)
                #    EAL_after = EAL_before × (new_vuln / old_vuln)
                vuln_before = asset_row.get("Vuln_asset", 0.0)
                if vuln_before > 0:
                    eal_after = eal_before * (new_vuln / vuln_before)
                else:
                    eal_after = eal_before * (1.0 - risk_reduction)
                eal_after = max(0.0, float(eal_after))
                
                # 4. Calculate ROI metrics using standard ROSI formula
                risk_reduction_usd = eal_before - eal_after
                # ROSI = (Risk_Reduction_usd − cost_usd) / cost_usd
                if cost_usd > 0:
                    rosi = (risk_reduction_usd - cost_usd) / cost_usd
                else:
                    rosi = float('inf')
                
                results.append({
                    "control_id": control_id,
                    "control_name": control_row["name"],
                    "asset_id": asset_id,
                    "cost_usd": cost_usd,
                    "EAL_before": eal_before,
                    "EAL_after": eal_after,
                    "Risk_Reduction_usd": risk_reduction_usd,
                    "ROSI": rosi
                })
                
        if not results:
            return pd.DataFrame(columns=[
                "control_id", "control_name", "asset_id", "cost_usd",
                "EAL_before", "EAL_after", "Risk_Reduction_usd", "ROSI"
            ])
            
        res_df = pd.DataFrame(results)
        # Sort by best ROSI
        res_df = res_df.sort_values(by="ROSI", ascending=False).reset_index(drop=True)
        return res_df
