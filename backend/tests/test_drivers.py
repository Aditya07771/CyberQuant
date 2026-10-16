"""Tests for risk_engine/drivers.py — EAL driver explainability."""
import pytest
import numpy as np
import pandas as pd

from risk_engine.drivers import explain_asset, _eal_simple
from risk_engine.config import EngineConfig


def _make_asset_row(
    tef_ml=5.0,
    vuln=0.4,
    lm_mean=100_000.0,
    vuln_list=None,
    risk_reduction_pct=0.3,
    business_unit="Finance",
) -> pd.Series:
    if vuln_list is None:
        vuln_list = [
            {"epss_score": 0.3, "cvss_score": 7.5, "is_kev": False},
            {"epss_score": 0.6, "cvss_score": 9.0, "is_kev": True},
        ]
    return pd.Series({
        "asset_id": "TEST-001",
        "TEF_mostlikely": tef_ml,
        "Vuln_asset": vuln,
        "LM_mean_usd": lm_mean,
        "vuln_list": vuln_list,
        "total_risk_reduction_pct": risk_reduction_pct,
        "business_unit": business_unit,
    })


def _make_full_df(asset_row: pd.Series) -> pd.DataFrame:
    """Create a small DataFrame with a few BU peers."""
    rows = [asset_row.to_dict()]
    for i in range(3):
        r = asset_row.to_dict()
        r["asset_id"] = f"PEER-{i}"
        r["TEF_mostlikely"] = 2.0 + i
        rows.append(r)
    return pd.DataFrame(rows)


def test_explain_asset_returns_list():
    row = _make_asset_row()
    df = _make_full_df(row)
    drivers = explain_asset(row, df)
    assert isinstance(drivers, list)
    assert len(drivers) >= 1


def test_drivers_sorted_descending():
    """Deltas must be sorted descending."""
    row = _make_asset_row()
    df = _make_full_df(row)
    drivers = explain_asset(row, df)
    deltas = [d["delta_usd"] for d in drivers]
    assert deltas == sorted(deltas, reverse=True)


def test_driver_keys_present():
    row = _make_asset_row()
    df = _make_full_df(row)
    drivers = explain_asset(row, df)
    for d in drivers:
        assert "driver" in d
        assert "delta_usd" in d


def test_controls_removed_driver_positive():
    """The 'Controls removed' driver should show a positive delta (controls save money)."""
    row = _make_asset_row(risk_reduction_pct=0.7)
    df = _make_full_df(row)
    drivers = explain_asset(row, df)
    ctrl_driver = next((d for d in drivers if "Controls removed" in d["driver"]), None)
    assert ctrl_driver is not None, "Controls removed driver not found"
    assert ctrl_driver["delta_usd"] >= 0.0, "Controls should reduce (not increase) risk"


def test_eal_simple_formula():
    """EAL_simple = TEF * Vuln * LM_mean."""
    val = _eal_simple(5.0, 0.4, 100_000.0)
    assert np.isclose(val, 200_000.0)

    val_zero = _eal_simple(0.0, 0.4, 100_000.0)
    assert val_zero == 0.0
