"""
risk_engine/drivers.py
======================
Explains the top drivers of an asset's Expected Annual Loss (EAL) by computing
EAL_simple and re-computing it with one factor neutralised at a time.

EAL_simple = TEF_mostlikely × Vuln_asset × LM_mean_usd
             ("frequency × average loss" — a quick, interpretable estimate)

Four counterfactual deltas are reported:
  (a) worst_cve_removed  — remove the highest-EPSS CVE from the asset's list
  (b) kev_flag_off       — treat all KEV-flagged CVEs as non-KEV
  (c) controls_removed   — set total_risk_reduction_pct = 0 (shows control value)
  (d) tef_to_median      — replace TEF_mostlikely with the business-unit median

Each delta_usd is (EAL_simple_baseline − EAL_simple_neutralised), so positive
values mean that factor *increases* risk.  The list is sorted descending by delta.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any

from .config import EngineConfig, DEFAULT_CONFIG
from .likelihood import LikelihoodModel


def _eal_simple(tef_ml: float, vuln: float, lm_mean: float) -> float:
    """EAL_simple = TEF_mostlikely × Vuln_asset × LM_mean_usd."""
    return max(0.0, float(tef_ml) * float(vuln) * float(lm_mean))


def explain_asset(
    asset_row: pd.Series,
    full_df: pd.DataFrame,
    config: EngineConfig = DEFAULT_CONFIG,
) -> List[Dict[str, Any]]:
    """
    Compute EAL_simple for the asset and re-compute with one factor neutralised
    at a time.  Returns a list of {driver, delta_usd} sorted descending by delta.

    Parameters
    ----------
    asset_row : pd.Series
        One row from the fully-processed asset DataFrame (post simulate).
    full_df : pd.DataFrame
        Full asset DataFrame — used to compute the business-unit median TEF.
    config : EngineConfig
        Engine configuration.

    Returns
    -------
    list of {driver: str, delta_usd: float}
    """
    likelihood_model = LikelihoodModel(config)

    tef_ml = float(asset_row.get("TEF_mostlikely", 0.0))
    vuln = float(asset_row.get("Vuln_asset", 0.0))
    lm_mean = float(asset_row.get("LM_mean_usd", 0.0))

    baseline = _eal_simple(tef_ml, vuln, lm_mean)

    drivers = []

    # ── (a) Remove the worst CVE (highest EPSS * CVSS) ───────────────────
    vuln_list = asset_row.get("vuln_list", []) or []
    if len(vuln_list) > 1:
        # Score each CVE by p_annual × severity_norm (same as likelihood model)
        def _score(v):
            try:
                p = likelihood_model.annualize_epss(v["epss_score"])
                s = likelihood_model.normalize_cvss(v["cvss_score"])
                return p * s
            except Exception:
                return 0.0

        scored = sorted(vuln_list, key=_score, reverse=True)
        reduced_list = scored[1:]  # remove worst
        reduced_row = asset_row.copy()
        reduced_row["vuln_list"] = reduced_list
        new_vuln = likelihood_model.calculate_vulnerability(reduced_row)
        alt_eal = _eal_simple(tef_ml, new_vuln, lm_mean)
        drivers.append({
            "driver": "Worst CVE removed",
            "delta_usd": baseline - alt_eal,
        })

    # ── (b) KEV flag off ──────────────────────────────────────────────────
    kev_vulns = [v for v in vuln_list if v.get("is_kev", False)]
    if kev_vulns:
        no_kev_list = [{**v, "is_kev": False} for v in vuln_list]
        reduced_row = asset_row.copy()
        reduced_row["vuln_list"] = no_kev_list
        new_vuln = likelihood_model.calculate_vulnerability(reduced_row)
        alt_eal = _eal_simple(tef_ml, new_vuln, lm_mean)
        drivers.append({
            "driver": "KEV flag removed",
            "delta_usd": baseline - alt_eal,
        })

    # ── (c) All controls removed (shows current control value) ────────────
    no_ctrl_row = asset_row.copy()
    no_ctrl_row["total_risk_reduction_pct"] = 0.0
    new_vuln = likelihood_model.calculate_vulnerability(no_ctrl_row)
    alt_eal = _eal_simple(tef_ml, new_vuln, lm_mean)
    drivers.append({
        "driver": "Controls removed (saved risk)",
        "delta_usd": alt_eal - baseline,  # flipped: controls REDUCE risk
    })

    # ── (d) TEF set to BU median ─────────────────────────────────────────
    bu = asset_row.get("business_unit", None)
    if bu is not None and "TEF_mostlikely" in full_df.columns and "business_unit" in full_df.columns:
        bu_tefs = full_df[full_df["business_unit"] == bu]["TEF_mostlikely"].dropna()
        if len(bu_tefs) > 1:
            bu_median = float(bu_tefs.median())
            if abs(bu_median - tef_ml) > 1e-9:
                alt_eal = _eal_simple(bu_median, vuln, lm_mean)
                drivers.append({
                    "driver": "TEF set to BU median",
                    "delta_usd": baseline - alt_eal,
                })

    # Sort descending by absolute delta, keep positive-delta items first
    drivers.sort(key=lambda d: d["delta_usd"], reverse=True)
    return drivers
