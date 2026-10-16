import pytest
import pandas as pd
import numpy as np

from risk_engine.frequency import FrequencyModel
from risk_engine.config import EngineConfig

@pytest.fixture
def frequency_model():
    return FrequencyModel(EngineConfig(min_events_for_asset_tef=3))

def test_apply_to_dataframe_insufficient_data(frequency_model):
    # Setup dataframe where an asset has 1 event (insufficient, < 3)
    # The BU has 3 assets: 1 event, 10 events, 20 events
    # annual_counts (approx * 12.16): ~12, ~121, ~243
    # For the asset with 1 event, it should fall back to BU percentiles
    df = pd.DataFrame([
        {"asset_id": "A1", "business_unit": "BU1", "event_count_raw": 1},
        {"asset_id": "A2", "business_unit": "BU1", "event_count_raw": 10},
        {"asset_id": "A3", "business_unit": "BU1", "event_count_raw": 20},
    ])
    
    result = frequency_model.apply_to_dataframe(df)
    
    a1 = result[result["asset_id"] == "A1"].iloc[0]
    
    # Check that A1 used BU Aggregate
    assert a1["TEF_source"] == "Business Unit Aggregate"
    
    # BU percentiles should be calculated on [1*12.16, 10*12.16, 20*12.16]
    counts = [1 * frequency_model.config.annualization_factor, 
              10 * frequency_model.config.annualization_factor, 
              20 * frequency_model.config.annualization_factor]
    
    assert np.isclose(a1["TEF_mostlikely"], np.median(counts))
    assert np.isclose(a1["TEF_min"], np.percentile(counts, 25))
    assert np.isclose(a1["TEF_max"], np.percentile(counts, 95))

def test_apply_to_dataframe_sufficient_data(frequency_model):
    # Setup dataframe where an asset has 10 events (sufficient, >= 3)
    df = pd.DataFrame([
        {"asset_id": "A1", "business_unit": "BU1", "event_count_raw": 2},
        {"asset_id": "A2", "business_unit": "BU1", "event_count_raw": 10},
        {"asset_id": "A3", "business_unit": "BU1", "event_count_raw": 20},
    ])
    
    result = frequency_model.apply_to_dataframe(df)
    
    a2 = result[result["asset_id"] == "A2"].iloc[0]
    
    # Check that A2 used Asset Historical
    assert a2["TEF_source"] == "Asset Historical"
    
    expected_ml = 10 * frequency_model.config.annualization_factor
    assert np.isclose(a2["TEF_mostlikely"], expected_ml)
    
    # Check that min and max are scaled relative to BU
    counts = [2 * frequency_model.config.annualization_factor, 
              10 * frequency_model.config.annualization_factor, 
              20 * frequency_model.config.annualization_factor]
    bu_p50 = np.median(counts)
    bu_p25 = np.percentile(counts, 25)
    bu_p95 = np.percentile(counts, 95)
    
    expected_min = expected_ml * (bu_p25 / bu_p50)
    expected_max = expected_ml * (bu_p95 / bu_p50)
    
    assert np.isclose(a2["TEF_min"], expected_min)
    assert np.isclose(a2["TEF_max"], expected_max)
    
    # Verify bounds
    assert a2["TEF_min"] <= a2["TEF_mostlikely"] <= a2["TEF_max"]

def test_apply_to_dataframe_zero_median(frequency_model):
    # If BU has median 0, it should fallback safely
    df = pd.DataFrame([
        {"asset_id": "A1", "business_unit": "BU1", "event_count_raw": 0},
        {"asset_id": "A2", "business_unit": "BU1", "event_count_raw": 0},
        {"asset_id": "A3", "business_unit": "BU1", "event_count_raw": 5},
    ])
    
    result = frequency_model.apply_to_dataframe(df)
    a3 = result[result["asset_id"] == "A3"].iloc[0]
    
    # Even though A3 has 5 events, BU median is 0, so ratio logic would div by 0.
    # Implementation should fallback to BU Aggregate
    assert a3["TEF_source"] == "Business Unit Aggregate"
    assert a3["TEF_mostlikely"] == 0.0
