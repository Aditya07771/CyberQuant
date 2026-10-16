import pytest
import pandas as pd
import numpy as np

from risk_engine.loss_magnitude import LossMagnitudeModel
from risk_engine.config import EngineConfig

def test_loss_magnitude_calculation():
    config = EngineConfig(ir_flat_cost_usd=10000.0, default_records_at_risk=5000)
    config.per_record_cost_usd = {"Public": 50.0}
    model = LossMagnitudeModel(config)
    
    df = pd.DataFrame([
        {
            "asset_id": "A1",
            "business_unit": "BU1",
            "downtime_cost_per_hour_usd": 1000.0,
            "avg_downtime_hours": 10.0,
            "data_sensitivity_tier": "Public",
            "avg_records_compromised": 1000,
            "regulatory_penalty_potential_usd": 0.0
        },
        {
            "asset_id": "A2",
            "business_unit": "BU1",
            "downtime_cost_per_hour_usd": 2000.0,
            "avg_downtime_hours": 0.0, # Will fall back to BU avg (5.0)
            "data_sensitivity_tier": "Public",
            "avg_records_compromised": 0, # Will fall back to BU avg (500)
            "regulatory_penalty_potential_usd": 50000.0
        }
    ])
    
    res = model.apply_to_dataframe(df)
    
    # A1 check
    a1 = res[res["asset_id"] == "A1"].iloc[0]
    expected_primary = (1000.0 * 10.0) + 10000.0
    expected_secondary = (1000 * 50.0)
    assert a1["LM_primary_usd"] == expected_primary
    assert a1["LM_secondary_usd"] == expected_secondary
    assert a1["LM_total_mostlikely_usd"] == expected_primary + expected_secondary
    assert np.isclose(a1["LM_lognormal_mu"], np.log(expected_primary + expected_secondary))
    
    # A2 check
    a2 = res[res["asset_id"] == "A2"].iloc[0]
    # BU avgs: downtime = 5.0, records = 500
    expected_primary_a2 = (2000.0 * 5.0) + 10000.0
    expected_secondary_a2 = (500 * 50.0) + 50000.0
    assert a2["LM_primary_usd"] == expected_primary_a2
    assert a2["LM_secondary_usd"] == expected_secondary_a2
