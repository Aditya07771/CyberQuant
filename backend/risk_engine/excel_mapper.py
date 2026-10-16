"""
Excel ingestion support for the Cyber Risk Quantification Engine.

The risk engine's authoritative schema is 5 relational tables
(assets, controls, asset_controls, threat_events, vulnerabilities).
Raw business spreadsheets — such as a financial card / account dataset
("Financial Transactions.xlsx") — do not follow that schema, so this
module:

1. Produces an auditable "Excel File Summary" (file name, row/column
   counts, worksheets, dataset type and per-column descriptions) that the
   dashboard can display to the user.
2. Normalises a financial card/account workbook into the 5 risk-engine
   tables via a documented, deterministic mapping, so the Monte Carlo FAIR
   pipeline can quantify the portfolio.

Everything here is transparent and rule-based (no randomness) so that any
derived risk number remains traceable.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Human-readable descriptions for the known financial card schema.
CARD_COLUMN_DESCRIPTIONS: Dict[str, str] = {
    "id": "Card record ID",
    "client_id": "Customer ID",
    "card_brand": "Card brand, such as Visa",
    "card_type": "Debit or credit card",
    "card_number": "Card number",
    "expires": "Card expiry date",
    "cvv": "Card security code",
    "has_chip": "Whether the card has a chip",
    "num_cards_issued": "Number of cards issued",
    "credit_limit": "Card credit limit",
    "acct_open_date": "Account opening date",
    "year_pin_last_changed": "Year the PIN was last changed",
    "card_on_dark_web": "Whether the card is reported on the dark web",
}

# A dataframe is considered "card data" when several of these columns exist.
CARD_SIGNATURE_COLUMNS = {
    "card_number", "client_id", "credit_limit", "card_on_dark_web", "card_brand",
}

# Synthetic control catalog derived from the measurable card attributes.
# Costs are per-card estimates (USD) and reductions are fractional (0-1),
# consistent with the engine's controls.csv contract.
CARD_CONTROLS: List[Dict[str, Any]] = [
    {
        "control_id": "CTRL-CHIP",
        "name": "EMV Chip & PIN Protection",
        "risk_reduction_pct": 0.40,
        "cost_usd": 4.0,
    },
    {
        "control_id": "CTRL-DARKWEB",
        "name": "Dark Web Card Monitoring & Alerts",
        "risk_reduction_pct": 0.65,
        "cost_usd": 15.0,
    },
    {
        "control_id": "CTRL-PINROT",
        "name": "Periodic PIN Rotation Policy",
        "risk_reduction_pct": 0.25,
        "cost_usd": 2.0,
    },
    {
        "control_id": "CTRL-3DS",
        "name": "3-D Secure Authentication",
        "risk_reduction_pct": 0.55,
        "cost_usd": 11.0,
    },
]

_MITRE_TECHNIQUES = [
    ("T1078", "Valid Accounts"),
    ("T1110", "Brute Force"),
    ("T1003", "OS Credential Dumping"),
    ("T1566", "Phishing"),
    ("T1552", "Unsecured Credentials"),
]


def _norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def _truthy(value: Any) -> bool:
    """Interprets common yes/no style encodings as booleans."""
    if value is None:
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            if np.isnan(value):
                return False
        except (TypeError, ValueError):
            pass
        return float(value) != 0.0
    text = str(value).strip().lower()
    return text in {"yes", "y", "true", "t", "1", "1.0", "on"}


def is_card_dataset(df: pd.DataFrame) -> bool:
    """Detects whether a dataframe carries the financial card/account schema."""
    if df is None or df.empty:
        return False
    cols = {str(c).strip().lower() for c in df.columns}
    return len(cols & CARD_SIGNATURE_COLUMNS) >= 2


def _infer_dataset_type(df: pd.DataFrame) -> str:
    if is_card_dataset(df):
        return "Financial card and account information."
    return "Tabular dataset"


def build_excel_summary(
    df: pd.DataFrame,
    file_name: str,
    sheet_names: Optional[List[str]] = None,
    dataset_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds the "Excel File Summary" structure surfaced in the dashboard."""
    sheet_names = sheet_names or ["Sheet1"]
    norm = _norm_columns(df) if df is not None else pd.DataFrame()

    column_details = []
    if not norm.empty:
        for col in norm.columns:
            column_details.append({
                "column": col,
                "description": CARD_COLUMN_DESCRIPTIONS.get(col, "—"),
                "dtype": str(norm[col].dtype),
            })

    return {
        "file_name": file_name,
        "total_rows": int(len(norm)),
        "total_columns": int(norm.shape[1]),
        "worksheets": sheet_names,
        "worksheet_count": len(sheet_names),
        "dataset_type": dataset_type or _infer_dataset_type(norm),
        "column_details": column_details,
    }


def _criticality_from(series: pd.Series) -> pd.Series:
    """Buckets a numeric series into 1-5 criticality levels via quintiles."""
    try:
        ranks = series.rank(method="first")
        buckets = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5])
        return buckets.astype(int)
    except (ValueError, TypeError):
        return pd.Series([3] * len(series), index=series.index)


def _unique(prefixes: List[str]) -> List[str]:
    seen: Dict[str, int] = {}
    out: List[str] = []
    for value in prefixes:
        if value in seen:
            seen[value] += 1
            out.append(f"{value}-{seen[value]}")
        else:
            seen[value] = 0
            out.append(value)
    return out


def _group_keys_for(
    n: int,
    max_assets: int,
    raw_ids: List[str],
    business_unit: pd.Series,
    card_type: pd.Series,
    has_chip: pd.Series,
    dark_web: pd.Series,
    credit: pd.Series,
) -> List[str]:
    """Assigns each card to an asset group.

    Small datasets keep one asset per card. Large datasets are aggregated
    into bounded risk segments (brand x product x chip x dark-web x credit
    quintile) so the downstream ILP frontier and Monte Carlo stay responsive,
    while every source record still contributes to a segment.
    """
    if n <= max_assets:
        return _unique([f"CRD-{rid}" for rid in raw_ids])

    buckets = pd.qcut(credit.rank(method="first"), 5, labels=False, duplicates="drop")
    buckets = pd.Series(buckets).fillna(0).astype(int)

    segment_keys = [
        f"{business_unit.iloc[i]}|{card_type.iloc[i] or 'na'}|"
        f"{'chip' if has_chip.iloc[i] else 'nochip'}|"
        f"{'dark' if dark_web.iloc[i] else 'clean'}|b{int(buckets.iloc[i])}"
        for i in range(n)
    ]

    if len(set(segment_keys)) <= max_assets:
        return segment_keys

    # Safety net: deterministic exposure-ranked chunking guarantees <= max_assets.
    chunk_size = max(1, int(np.ceil(n / max_assets)))
    order = credit.rank(method="first", ascending=False).astype(int) - 1
    return [f"SEG-{int(o // chunk_size) + 1:04d}" for o in order]


def map_cards_to_risk_tables(
    card_df: pd.DataFrame,
    max_assets: int = 400,
    max_events: int = 2000,
) -> Dict[str, pd.DataFrame]:
    """
    Deterministically maps a financial card/account dataframe onto the risk
    engine's 5-table schema.

    Mapping summary (documented assumptions):
      * assets        : one row per card for small datasets; larger datasets
                        are aggregated into bounded risk segments. card id ->
                        asset_id; credit_limit -> financial_value_usd; brand ->
                        business_unit; dark-web status / card type ->
                        data_sensitivity_tier.
      * controls      : synthetic catalog of card-security controls.
      * asset_controls: controls implied by has_chip / dark-web / PIN age /
                        credit product.
      * threat_events : synthetic SIEM-style events for risky segments, spread
                        across the last 30 days (feeds TEF + LSTM forecaster).
      * vulnerabilities: one synthetic credential/CVE-style row per asset,
                        scored from the asset's measured risk factors.
    """
    if card_df is None or card_df.empty:
        raise ValueError("Card dataframe is empty; cannot map to risk tables.")

    df = _norm_columns(card_df)
    n = len(df)

    # --- Identity ---------------------------------------------------------
    if "id" in df.columns:
        raw_ids = df["id"].astype(str).tolist()
    else:
        raw_ids = [str(i + 1) for i in range(n)]

    # --- Numeric factors --------------------------------------------------
    credit = (
        pd.to_numeric(df["credit_limit"], errors="coerce")
        if "credit_limit" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    credit = credit.fillna(credit.median() if credit.notna().any() else 1000.0)
    credit = credit.clip(lower=0.0).astype(float)

    num_cards = (
        pd.to_numeric(df["num_cards_issued"], errors="coerce")
        if "num_cards_issued" in df.columns
        else pd.Series(1.0, index=df.index)
    )
    num_cards = num_cards.fillna(1.0).clip(lower=1.0).astype(float)

    dark_web = (
        df["card_on_dark_web"].apply(_truthy)
        if "card_on_dark_web" in df.columns
        else pd.Series(False, index=df.index)
    )
    has_chip = (
        df["has_chip"].apply(_truthy)
        if "has_chip" in df.columns
        else pd.Series(True, index=df.index)
    )
    card_type = (
        df["card_type"].astype(str).str.strip().str.lower()
        if "card_type" in df.columns
        else pd.Series("", index=df.index)
    )
    card_brand = (
        df["card_brand"].astype(str).str.strip()
        if "card_brand" in df.columns
        else pd.Series("", index=df.index)
    )
    business_unit = card_brand.where(card_brand.str.len() > 0, "Unknown")
    business_unit = business_unit.where(business_unit != "nan", "Unknown")

    current_year = datetime.now(timezone.utc).year
    year_pin = (
        pd.to_numeric(df["year_pin_last_changed"], errors="coerce")
        if "year_pin_last_changed" in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    pin_age = (current_year - year_pin).clip(lower=0, upper=20).fillna(10.0)

    # --- Normalised risk index (0-1) -------------------------------------
    credit_span = float(credit.max() - credit.min())
    credit_norm = (credit - credit.min()) / credit_span if credit_span > 0 else pd.Series(0.5, index=df.index)
    risk_index = (
        0.45 * dark_web.astype(float)
        + 0.25 * (~has_chip).astype(float)
        + 0.20 * credit_norm
        + 0.10 * (pin_age / 20.0)
    ).clip(0.0, 1.0)

    # --- Assign cards to asset groups ------------------------------------
    group_keys = _group_keys_for(
        n, max_assets, raw_ids, business_unit, card_type, has_chip, dark_web, credit
    )
    per_card = n <= max_assets

    work = pd.DataFrame({
        "group_key": group_keys,
        "raw_id": raw_ids,
        "brand": business_unit.values,
        "is_credit": (card_type == "credit").values,
        "dark": dark_web.values.astype(bool),
        "chip": has_chip.values.astype(bool),
        "pin_recent": (pin_age <= 2).values,
        "credit": credit.values,
        "num_cards": num_cards.values,
        "risk_index": risk_index.values,
    })

    def _mode(series: pd.Series) -> str:
        modes = series.mode()
        return modes.iloc[0] if not modes.empty else "Unknown"

    agg = work.groupby("group_key", sort=False).agg(
        brand=("brand", _mode),
        is_credit=("is_credit", "any"),
        dark=("dark", "any"),
        chip_frac=("chip", "mean"),
        pin_recent=("pin_recent", "any"),
        credit=("credit", "sum"),
        num_cards=("num_cards", "sum"),
        risk_index=("risk_index", "mean"),
        first_raw=("raw_id", "first"),
        card_count=("raw_id", "count"),
    ).reset_index()

    n_groups = len(agg)
    if per_card:
        agg["asset_id"] = [f"CRD-{r}" for r in agg["first_raw"]]
    else:
        agg["asset_id"] = [f"SEG-{i + 1:04d}" for i in range(n_groups)]

    agg["criticality"] = _criticality_from(agg["credit"]).values
    agg["sensitivity"] = np.where(
        agg["dark"], "Restricted",
        np.where(agg["is_credit"], "Confidential", "Internal"),
    )

    # --- assets -----------------------------------------------------------
    assets = pd.DataFrame({
        "asset_id": agg["asset_id"].values,
        "business_unit": agg["brand"].values,
        "criticality": agg["criticality"].values,
        "data_sensitivity_tier": agg["sensitivity"].values,
        "financial_value_usd": agg["credit"].round(2).values,
        "downtime_cost_per_hour_usd": (agg["credit"] * 0.02).clip(lower=50.0).round(2).values,
        "regulatory_penalty_potential_usd": (agg["credit"] * 0.05 * agg["dark"].astype(float)).round(2).values,
    })

    # --- controls ---------------------------------------------------------
    controls = pd.DataFrame(CARD_CONTROLS)

    # --- asset_controls ---------------------------------------------------
    ac_rows: List[Dict[str, str]] = []
    for i in range(n_groups):
        asset_id = agg["asset_id"].iloc[i]
        if float(agg["chip_frac"].iloc[i]) >= 0.5:
            ac_rows.append({"asset_id": asset_id, "control_id": "CTRL-CHIP"})
        if bool(agg["dark"].iloc[i]):
            ac_rows.append({"asset_id": asset_id, "control_id": "CTRL-DARKWEB"})
        if bool(agg["pin_recent"].iloc[i]):
            ac_rows.append({"asset_id": asset_id, "control_id": "CTRL-PINROT"})
        if bool(agg["is_credit"].iloc[i]):
            ac_rows.append({"asset_id": asset_id, "control_id": "CTRL-3DS"})
    asset_controls = pd.DataFrame(ac_rows, columns=["asset_id", "control_id"])

    # --- threat_events ----------------------------------------------------
    agg_span = float(agg["credit"].max() - agg["credit"].min())
    agg_credit_norm = (agg["credit"] - agg["credit"].min()) / agg_span if agg_span > 0 else pd.Series(0.5, index=agg.index)
    event_priority = (
        agg["dark"].astype(int) * 3
        + (agg["chip_frac"] < 0.5).astype(int) * 2
        + (agg_credit_norm > 0.75).astype(int)
    )
    candidate_idx = [i for i in range(n_groups) if event_priority.iloc[i] > 0]
    candidate_idx.sort(key=lambda i: (-event_priority.iloc[i], -agg["credit"].iloc[i]))
    candidate_idx = candidate_idx[:max_events]

    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    event_rows: List[Dict[str, Any]] = []
    for j, i in enumerate(candidate_idx):
        tech_id, tech_name = _MITRE_TECHNIQUES[j % len(_MITRE_TECHNIQUES)]
        is_dark = bool(agg["dark"].iloc[i])
        severity = "Critical" if (is_dark and j % 3 == 0) else ("High" if is_dark else "Medium")
        action_taken = "allowed" if j % 4 == 0 else "blocked"
        ts = base_time + timedelta(days=(j % 30), hours=(j * 3) % 24, minutes=(j * 7) % 60)
        event_rows.append({
            "event_id": f"EVT-{j + 1:05d}",
            "timestamp": ts.isoformat(),
            "asset_id": agg["asset_id"].iloc[i],
            "mitre_technique_id": tech_id,
            "description": f"{tech_name} attempt against {agg['asset_id'].iloc[i]}",
            "severity": severity,
            "source_ip": f"198.51.100.{(j % 250) + 1}",
            "action_taken": action_taken,
            "downtime_hours_caused": round(2.0 + float(agg["risk_index"].iloc[i]) * 46.0, 2),
            "records_compromised": int(agg["num_cards"].iloc[i]),
        })
    threat_events = pd.DataFrame(event_rows, columns=[
        "event_id", "timestamp", "asset_id", "mitre_technique_id", "description",
        "severity", "source_ip", "action_taken", "downtime_hours_caused",
        "records_compromised",
    ])

    # --- vulnerabilities --------------------------------------------------
    cvss = (4.0 + 4.5 * agg["risk_index"]).clip(0.1, 10.0).round(1)
    epss = (0.02 + 0.30 * agg["risk_index"]).clip(0.0, 1.0).round(4)
    discovery = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    vuln_severity = ["Critical" if s >= 9.0 else "High" if s >= 7.0 else "Medium" if s >= 4.0 else "Low" for s in cvss]
    vulnerabilities = pd.DataFrame({
        "asset_id": agg["asset_id"].values,
        "cve_id": [f"VULN-{aid}" for aid in agg["asset_id"].values],
        "cvss_score": cvss.values,
        "epss_score": epss.values,
        "severity": vuln_severity,
        "status": "open",
        "discovery_date": discovery,
    })

    logger.info(
        "Mapped %d card records -> %d assets (%s), %d controls, %d mappings, %d events, %d vulns",
        n, n_groups, "per-card" if per_card else "risk-segment", len(controls),
        len(asset_controls), len(threat_events), len(vulnerabilities),
    )

    return {
        "assets": assets,
        "controls": controls,
        "asset_controls": asset_controls,
        "threat_events": threat_events,
        "vulnerabilities": vulnerabilities,
    }
