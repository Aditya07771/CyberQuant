import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
import uuid

from risk_engine.config import EngineConfig
from risk_engine.ingest import DataIngestor, IngestionError

@pytest.fixture
def test_data_dir():
    """Creates a workspace-local temporary directory with dummy CSVs for testing."""
    test_id = uuid.uuid4().hex[:8]
    data_dir = Path(__file__).parent / f".test_data_{test_id}"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create valid assets
    assets = pd.DataFrame({
        "asset_id": ["A1", "A2"],
        "business_unit": ["Finance", "HR"],
        "criticality": [3, 4],
        "data_sensitivity_tier": ["Internal", "Confidential"],
        "financial_value_usd": [100000, 200000],
        "downtime_cost_per_hour_usd": [1000, 2000]
    })
    assets.to_csv(data_dir / "assets.csv", index=False)
    
    # Create valid vulns
    vulns = pd.DataFrame({
        "vuln_id": ["V1"],
        "asset_id": ["A1"],
        "cve_id": ["CVE-123"],
        "cvss_score": [5.5],
        "epss_score": [0.1]
    })
    vulns.to_csv(data_dir / "vulnerabilities.csv", index=False)
    
    # Create valid events
    events = pd.DataFrame({
        "event_id": ["E1", "E2"],
        "asset_id": ["A1", "A1"],
        "downtime_hours_caused": [0, 5],
        "records_compromised": [0, 100]
    })
    events.to_csv(data_dir / "threat_events.csv", index=False)
    
    # Create valid controls (risk_reduction_pct is a fraction!)
    controls = pd.DataFrame({
        "control_id": ["C1", "C2"],
        "risk_reduction_pct": [0.8, 0.5]
    })
    controls.to_csv(data_dir / "controls.csv", index=False)
    
    # Create valid asset_controls
    asset_controls = pd.DataFrame({
        "asset_id": ["A1", "A1"],
        "control_id": ["C1", "C2"]
    })
    asset_controls.to_csv(data_dir / "asset_controls.csv", index=False)
    
    yield data_dir
    shutil.rmtree(data_dir, ignore_errors=True)

@pytest.fixture
def ingestor(test_data_dir):
    config = EngineConfig(data_dir=test_data_dir)
    return DataIngestor(config=config)

def test_load_data_success(ingestor):
    data = ingestor.load_data()
    assert "assets" in data
    assert "vulnerabilities" in data
    assert "threat_events" in data
    assert "controls" in data
    assert "asset_controls" in data
    
    assert len(data["assets"]) == 2

def test_load_data_missing_file(test_data_dir):
    (test_data_dir / "assets.csv").unlink()
    config = EngineConfig(data_dir=test_data_dir)
    ingestor = DataIngestor(config=config)
    
    with pytest.raises(FileNotFoundError):
        ingestor.load_data()
        
def test_validation_negative_financial(test_data_dir):
    # Overwrite assets with negative value
    assets = pd.DataFrame({
        "asset_id": ["A1"],
        "business_unit": ["Finance"],
        "criticality": [3],
        "data_sensitivity_tier": ["Internal"],
        "financial_value_usd": [-100],  # Negative!
        "downtime_cost_per_hour_usd": [1000]
    })
    assets.to_csv(test_data_dir / "assets.csv", index=False)
    
    config = EngineConfig(data_dir=test_data_dir)
    ingestor = DataIngestor(config=config)
    
    with pytest.raises(IngestionError, match="Negative financial_value_usd"):
        ingestor.load_data()

def test_validation_invalid_risk_reduction(test_data_dir):
    # Overwrite controls with invalid fraction (percentage)
    controls = pd.DataFrame({
        "control_id": ["C1"],
        "risk_reduction_pct": [85.0]  # Should be 0.85
    })
    controls.to_csv(test_data_dir / "controls.csv", index=False)
    
    config = EngineConfig(data_dir=test_data_dir)
    ingestor = DataIngestor(config=config)
    
    with pytest.raises(IngestionError, match="must be between 0.0 and 1.0"):
        ingestor.load_data()
        
def test_build_asset_risk_base(ingestor):
    data = ingestor.load_data()
    base_df = ingestor.build_asset_risk_base(data)
    
    assert len(base_df) == 2
    
    # Asset A1 should have everything
    a1 = base_df[base_df["asset_id"] == "A1"].iloc[0]
    assert len(a1["vuln_list"]) == 1
    assert a1["event_count_raw"] == 2
    assert a1["avg_downtime_hours"] == 2.5
    assert a1["avg_records_compromised"] == 50.0
    
    # Default is now multiplicative: 1 - (1 - 0.8) * (1 - 0.5) = 1 - 0.1 = 0.9
    assert np.isclose(a1["total_risk_reduction_pct"], 0.9)
    assert len(a1["active_controls"]) == 2
    
    # Asset A2 should be empty
    a2 = base_df[base_df["asset_id"] == "A2"].iloc[0]
    assert len(a2["vuln_list"]) == 0
    assert a2["event_count_raw"] == 0
    assert a2["total_risk_reduction_pct"] == 0.0
    assert len(a2["active_controls"]) == 0

def test_additive_capped_control_aggregation(test_data_dir):
    config = EngineConfig(data_dir=test_data_dir, control_aggregation="additive_capped")
    ingestor = DataIngestor(config=config)
    data = ingestor.load_data()
    base_df = ingestor.build_asset_risk_base(data)
    
    a1 = base_df[base_df["asset_id"] == "A1"].iloc[0]
    # C1 (0.8) + C2 (0.5) = 1.3 -> capped to 1.0
    assert a1["total_risk_reduction_pct"] == 1.0

def test_multiplicative_control_aggregation(test_data_dir):
    config = EngineConfig(data_dir=test_data_dir, control_aggregation="multiplicative")
    ingestor = DataIngestor(config=config)
    data = ingestor.load_data()
    base_df = ingestor.build_asset_risk_base(data)
    
    a1 = base_df[base_df["asset_id"] == "A1"].iloc[0]
    # C1 (0.8) and C2 (0.5) -> 1 - (1-0.8)*(1-0.5) = 1 - (0.2*0.5) = 1 - 0.1 = 0.9
    assert np.isclose(a1["total_risk_reduction_pct"], 0.9)
