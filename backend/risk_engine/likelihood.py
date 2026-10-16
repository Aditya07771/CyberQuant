import pandas as pd
import numpy as np
from typing import Dict, Any

from .config import EngineConfig, DEFAULT_CONFIG

class LikelihoodModel:
    """Calculates FAIR-aligned vulnerability factor per asset."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        
    def annualize_epss(self, epss_score: float) -> float:
        """
        Converts 30-day EPSS probability into annual probability.
        Uses standard survival probability formula: P_annual = 1 - (1 - P_window)^(365/window)
        """
        if epss_score < 0 or epss_score > 1:
            raise ValueError(f"EPSS score must be between 0 and 1, got {epss_score}")
        
        exponent = 365.0 / self.config.epss_window_days
        p_annual = 1.0 - (1.0 - epss_score) ** exponent
        return p_annual
        
    def normalize_cvss(self, cvss_score: float) -> float:
        """
        Normalizes CVSS base score (0-10) to a 0-1 scale.
        """
        if cvss_score < 0 or cvss_score > 10:
            raise ValueError(f"CVSS score must be between 0 and 10, got {cvss_score}")
            
        return cvss_score / 10.0
        
    def calculate_vulnerability(self, asset_row: pd.Series) -> float:
        """
        Calculates the FAIR Vulnerability factor for a single asset.
        
        Vulnerability is the probability that a threat event succeeds.
        For each CVE:
            p_annual = annualize_epss(epss_score)
            if is_kev: p_annual = min(1.0, p_annual * kev_multiplier)
            vuln_cve = p_annual * severity_norm * (1 - control_resistance)
        Asset vulnerability = max(vuln_cve) across all CVEs on the asset.
        
        If the asset has no vulnerabilities, returns 0.0.
        """
        vuln_list = asset_row.get("vuln_list", [])
        if not vuln_list:
            return 0.0
            
        control_resistance = min(1.0, asset_row.get("total_risk_reduction_pct", 0.0))
        
        max_vuln = 0.0
        for vuln in vuln_list:
            p_annual = self.annualize_epss(vuln["epss_score"])
            
            # KEV flag: if True, multiply p_annual by kev_multiplier (cap at 1.0)
            is_kev = vuln.get("is_kev", False)
            if is_kev:
                p_annual = min(1.0, p_annual * self.config.kev_multiplier)
            
            severity_norm = self.normalize_cvss(vuln["cvss_score"])
            
            vuln_cve = p_annual * severity_norm * (1.0 - control_resistance)
            if vuln_cve > max_vuln:
                max_vuln = vuln_cve
                
        return max_vuln
        
    def apply_to_dataframe(self, base_df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies the vulnerability calculation to the entire asset_risk_base dataframe.
        Adds a 'Vuln_asset' column.
        """
        df = base_df.copy()
        df["Vuln_asset"] = df.apply(self.calculate_vulnerability, axis=1)
        return df
