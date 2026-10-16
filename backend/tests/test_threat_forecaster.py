import pytest
import pandas as pd
from risk_engine.threat_forecaster import ThreatSequenceForecaster

def test_threat_forecaster_execution():
    forecaster = ThreatSequenceForecaster(window_size=7, forecast_horizon=14)
    from pathlib import Path
    csv_path = Path("backend/data/threat_events.csv") if Path("backend/data/threat_events.csv").exists() else Path("data/threat_events.csv")
    df = pd.read_csv(csv_path)
    result = forecaster.train_and_forecast(df)
    
    assert "summary" in result
    assert "forecast_series" in result
    assert "historical_series" in result
    assert "mitre_transitions" in result
    
    summary = result["summary"]
    assert summary["forecast_horizon_days"] == 14
    assert len(result["forecast_series"]) == 14
    assert len(result["mitre_transitions"]) > 0
    assert "predicted_events" in result["forecast_series"][0]
