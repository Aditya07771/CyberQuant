import pandas as pd
import numpy as np

from .config import EngineConfig, DEFAULT_CONFIG

class FrequencyModel:
    """Calculates Threat Event Frequency (TEF) distributions per asset."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        
    def apply_to_dataframe(self, base_df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies TEF calculations to the asset_risk_base dataframe.
        Adds TEF_min, TEF_mostlikely, and TEF_max columns.
        """
        df = base_df.copy()
        
        # 1. Annualize the raw event count for each asset
        df["annual_event_count"] = df["event_count_raw"] * self.config.annualization_factor
        
        # 2. Compute Business Unit aggregates
        # We need the 25th, 50th, and 95th percentiles of annualized counts per BU
        bu_agg = df.groupby("business_unit")["annual_event_count"].agg(
            bu_p25=lambda x: np.percentile(x, 25),
            bu_p50=lambda x: np.median(x),
            bu_p95=lambda x: np.percentile(x, 95)
        ).reset_index()
        
        # Merge BU aggregates back to the main dataframe
        df = df.merge(bu_agg, on="business_unit", how="left")
        
        # 3. Calculate TEF for each asset
        def calculate_tef(row):
            annual_count = row["annual_event_count"]
            raw_count = row["event_count_raw"]
            
            p25 = row["bu_p25"]
            p50 = row["bu_p50"]
            p95 = row["bu_p95"]
            
            # If insufficient data or median is 0, use the BU aggregate directly
            if raw_count < self.config.min_events_for_asset_tef or p50 == 0:
                return pd.Series({
                    "TEF_min": p25,
                    "TEF_mostlikely": p50,
                    "TEF_max": p95,
                    "TEF_source": "Business Unit Aggregate"
                })
            else:
                # Asset has sufficient data. Use its own count as most likely.
                # Scale the BU's spread relative to the median.
                tef_ml = annual_count
                ratio_min = p25 / p50 if p50 > 0 else 0.5
                ratio_max = p95 / p50 if p50 > 0 else 2.0
                
                tef_min = tef_ml * ratio_min
                tef_max = tef_ml * ratio_max
                
                # Ensure logical bounds
                if tef_min > tef_ml:
                    tef_min = tef_ml
                if tef_max < tef_ml:
                    tef_max = tef_ml
                    
                # If all are exactly the same (no spread), add minimal variance 
                # so the triangular distribution doesn't fail
                if tef_min == tef_ml == tef_max:
                    tef_min = tef_ml * 0.9
                    tef_max = tef_ml * 1.1
                    
                return pd.Series({
                    "TEF_min": tef_min,
                    "TEF_mostlikely": tef_ml,
                    "TEF_max": tef_max,
                    "TEF_source": "Asset Historical"
                })
                
        tef_cols = df.apply(calculate_tef, axis=1)
        df = pd.concat([df, tef_cols], axis=1)
        
        # Clean up temporary columns
        df = df.drop(columns=["bu_p25", "bu_p50", "bu_p95"])
        return df
