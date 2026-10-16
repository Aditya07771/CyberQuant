import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from pathlib import Path

from .config import EngineConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)

class IngestionError(Exception):
    """Raised when data validation fails."""
    pass

class DataIngestor:
    """Handles loading, validation, and normalization of raw CSV data."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Loads all authoritative CSV files from the configured data directory."""
        data_dir = self.config.data_dir
        if not data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")
            
        required_files = [
            "assets.csv",
            "vulnerabilities.csv",
            "threat_events.csv",
            "controls.csv",
            "asset_controls.csv"
        ]
        
        data = {}
        for filename in required_files:
            file_path = data_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"Required data file missing: {file_path}")
            
            try:
                df = pd.read_csv(file_path)
                data[filename.replace(".csv", "")] = df
            except Exception as e:
                raise IngestionError(f"Failed to read {filename}: {e}")
                
        self._validate_schemas(data)
        return data
        
    def _validate_schemas(self, data: Dict[str, pd.DataFrame]) -> None:
        """Validates critical columns exist and have correct types."""
        
        # Check assets
        assets = data["assets"]
        required_asset_cols = [
            "asset_id", "business_unit", "criticality", "data_sensitivity_tier",
            "financial_value_usd", "downtime_cost_per_hour_usd"
        ]
        for col in required_asset_cols:
            if col not in assets.columns:
                raise IngestionError(f"Missing required column '{col}' in assets.csv")
                
        # Reject negative financial values
        if (assets["financial_value_usd"] < 0).any():
            raise IngestionError("Negative financial_value_usd found in assets.csv")
        if (assets["downtime_cost_per_hour_usd"] < 0).any():
            raise IngestionError("Negative downtime_cost_per_hour_usd found in assets.csv")
            
        # Check controls
        controls = data["controls"]
        if "risk_reduction_pct" not in controls.columns:
            raise IngestionError("Missing 'risk_reduction_pct' in controls.csv")
            
        # Ensure risk_reduction_pct is 0-1 range (fraction)
        if (controls["risk_reduction_pct"] > 1.0).any() or (controls["risk_reduction_pct"] < 0.0).any():
            raise IngestionError("risk_reduction_pct in controls.csv must be between 0.0 and 1.0")

    def build_asset_risk_base(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Builds the normalized 'asset_risk_base' DataFrame.
        One row per asset, combining vulnerabilities, events, and controls.
        """
        assets_df = data["assets"].copy()
        vulns_df = data["vulnerabilities"].copy()
        events_df = data["threat_events"].copy()
        controls_df = data["controls"].copy()
        asset_controls_df = data["asset_controls"].copy()
        
        # 1. Aggregate vulnerabilities per asset
        vuln_agg = vulns_df.groupby("asset_id").apply(
            lambda x: x[["cve_id", "cvss_score", "epss_score"]].to_dict(orient="records"),
            include_groups=False,
        ).reset_index(name="vuln_list")
        
        # 2. Aggregate threat events per asset
        event_agg = events_df.groupby("asset_id").agg(
            event_count_raw=("event_id", "count"),
            avg_downtime_hours=("downtime_hours_caused", "mean"),
            avg_records_compromised=("records_compromised", "mean")
        ).reset_index()
        
        # 3. Aggregate controls per asset
        # First join asset_controls with controls to get risk_reduction_pct
        ac_joined = asset_controls_df.merge(controls_df, on="control_id", how="left")
        
        # Group by asset
        def combine_controls(group):
            active_controls = group["control_id"].tolist()
            if self.config.control_aggregation == "additive_capped":
                total_reduction = min(1.0, group["risk_reduction_pct"].sum())
            else:
                # multiplicative
                # total = 1 - product(1 - pct)
                total_reduction = 1.0 - np.prod(1.0 - group["risk_reduction_pct"].values)
            return pd.Series({
                "active_controls": active_controls,
                "total_risk_reduction_pct": total_reduction
            })
            
        control_agg = ac_joined.groupby("asset_id").apply(combine_controls, include_groups=False).reset_index()
        
        # 4. Join everything to assets_df
        base_df = assets_df.merge(vuln_agg, on="asset_id", how="left")
        base_df = base_df.merge(event_agg, on="asset_id", how="left")
        base_df = base_df.merge(control_agg, on="asset_id", how="left")
        
        # Fill missing values
        base_df["vuln_list"] = base_df["vuln_list"].apply(lambda x: x if isinstance(x, list) else [])
        base_df["event_count_raw"] = base_df["event_count_raw"].fillna(0)
        base_df["avg_downtime_hours"] = base_df["avg_downtime_hours"].fillna(0)
        base_df["avg_records_compromised"] = base_df["avg_records_compromised"].fillna(0)
        base_df["active_controls"] = base_df["active_controls"].apply(lambda x: x if isinstance(x, list) else [])
        base_df["total_risk_reduction_pct"] = base_df["total_risk_reduction_pct"].fillna(0.0)
        
        # Log warnings for unprotected assets
        unprotected_count = (base_df["total_risk_reduction_pct"] == 0).sum()
        if unprotected_count > 0:
            logger.warning(f"Found {unprotected_count} assets with zero deployed controls.")
            
        no_vuln_count = base_df["vuln_list"].apply(len).eq(0).sum()
        if no_vuln_count > 0:
            logger.info(f"Found {no_vuln_count} assets with no vulnerabilities.")
            
        return base_df
