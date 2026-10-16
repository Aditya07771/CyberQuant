import pytest
import pandas as pd
import numpy as np

from risk_engine.likelihood import LikelihoodModel
from risk_engine.config import EngineConfig

@pytest.fixture
def likelihood_model():
    return LikelihoodModel(EngineConfig())

def test_epss_annualization(likelihood_model):
    # If 30-day prob is 0.1, annual prob should be 1 - (1 - 0.1)^(365/30)
    # exponent = 12.1666...
    # (1 - 0.1)^12.1666 = 0.9^12.1666 ≈ 0.277
    # annual ≈ 1 - 0.277 = 0.723
    p_30 = 0.1
    p_annual = likelihood_model.annualize_epss(p_30)
    
    expected = 1.0 - (1.0 - p_30) ** (365.0 / 30.0)
    assert np.isclose(p_annual, expected)
    assert 0.0 <= p_annual <= 1.0

def test_epss_annualization_bounds(likelihood_model):
    assert np.isclose(likelihood_model.annualize_epss(0.0), 0.0)
    assert np.isclose(likelihood_model.annualize_epss(1.0), 1.0)
    
    with pytest.raises(ValueError):
        likelihood_model.annualize_epss(1.5)
        
    with pytest.raises(ValueError):
        likelihood_model.annualize_epss(-0.1)

def test_cvss_normalization(likelihood_model):
    assert np.isclose(likelihood_model.normalize_cvss(0.0), 0.0)
    assert np.isclose(likelihood_model.normalize_cvss(5.5), 0.55)
    assert np.isclose(likelihood_model.normalize_cvss(10.0), 1.0)
    
    with pytest.raises(ValueError):
        likelihood_model.normalize_cvss(11.0)

def test_vulnerability_calculation(likelihood_model):
    asset_row = pd.Series({
        "vuln_list": [
            {"epss_score": 0.1, "cvss_score": 5.0}, # p_ann≈0.72, norm_cvss=0.5 -> base=0.36
            {"epss_score": 0.5, "cvss_score": 10.0} # p_ann≈0.9997, norm_cvss=1.0 -> base≈1.0
        ],
        "total_risk_reduction_pct": 0.8 # control_resistance = 0.8
    })
    
    # Expected max is from the second vuln: ~1.0 * (1 - 0.8) = 0.2
    vuln = likelihood_model.calculate_vulnerability(asset_row)
    
    p_ann_1 = likelihood_model.annualize_epss(0.1)
    p_ann_2 = likelihood_model.annualize_epss(0.5)
    
    expected = max(
        p_ann_1 * 0.5 * (1 - 0.8),
        p_ann_2 * 1.0 * (1 - 0.8)
    )
    
    assert np.isclose(vuln, expected)

def test_vulnerability_no_vulns(likelihood_model):
    asset_row = pd.Series({
        "vuln_list": [],
        "total_risk_reduction_pct": 0.0
    })
    assert likelihood_model.calculate_vulnerability(asset_row) == 0.0

def test_apply_to_dataframe(likelihood_model):
    df = pd.DataFrame([
        {
            "asset_id": "A1",
            "vuln_list": [{"epss_score": 0.1, "cvss_score": 10.0}],
            "total_risk_reduction_pct": 0.0
        },
        {
            "asset_id": "A2",
            "vuln_list": [],
            "total_risk_reduction_pct": 0.5
        }
    ])
    
    result = likelihood_model.apply_to_dataframe(df)
    assert "Vuln_asset" in result.columns
    assert result.iloc[0]["Vuln_asset"] > 0
    assert result.iloc[1]["Vuln_asset"] == 0.0
