"""
Configuration module for the Cyber Risk Quantification Engine.

All tuneable parameters, documented assumptions, and constants live here.
Every assumption is annotated with its source/justification so that any
calculated risk number can be traced back to its configuration origin.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass
class EngineConfig:
    """Central configuration for the risk quantification pipeline.

    Every field is documented with its purpose, default value, and the
    rationale behind the default.  Change defaults here — not buried
    inside calculation modules — so that the pipeline remains auditable.
    """

    # ── Random seed & simulation count ────────────────────────────────
    random_seed: int = 42
    """Seed for NumPy RNG.  Ensures reproducible Monte Carlo results."""

    n_simulations: int = 20_000
    """Number of Monte Carlo iterations per asset.  20 000 gives stable
    percentile estimates while remaining fast on commodity hardware."""

    # ── File paths ────────────────────────────────────────────────────
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "data")
    """Directory containing the 5 authoritative CSV files."""

    output_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "outputs")
    """Directory where parquet outputs are written."""

    # ── Threat-event time window ──────────────────────────────────────
    data_timespan_days: float = 30.0
    """Calendar days spanned by threat_events.csv.
    Inspected value: events run from ~2026-07-28 to ~2026-08-26 ≈ 30 d.
    Used to annualise raw event counts via  annual = raw × (365 / data_timespan_days)."""

    annualization_factor: float = 365.0 / 30.0
    """Derived: 365 / data_timespan_days.  Pre-computed for clarity."""

    # ── TEF estimation ────────────────────────────────────────────────
    min_events_for_asset_tef: int = 3
    """If an asset has fewer than this many events in the observation
    window, borrow the business-unit aggregate TEF instead.
    Documented assumption: sparse per-asset data is unreliable."""

    # ── Loss magnitude — incident response ────────────────────────────
    ir_flat_cost_usd: float = 25_000.0
    """Flat incident-response cost per loss event.
    Source: IBM/Ponemon 2024 Cost of a Data Breach Report — detection
    and escalation cost component (~$25k median for mid-size orgs).
    This is a documented assumption; replace with org-specific data if available."""

    # ── Loss magnitude — per-record breach cost by sensitivity tier ───
    per_record_cost_usd: Dict[str, float] = field(default_factory=lambda: {
        "Public":       50.0,
        "Internal":    100.0,
        "Confidential": 165.0,
        "Restricted":  250.0,
    })
    """Per-record breach cost (USD) indexed by data_sensitivity_tier.
    Source: IBM/Ponemon 2024 global average is $165/record.  Tiers are
    scaled around that anchor: Public < Internal < Confidential (anchor) < Restricted.
    Documented assumption — cite the report year in any deliverable."""

    # ── Loss magnitude — estimated records at risk (fallback) ─────────
    default_records_at_risk: int = 10_000
    """If an asset has no historical records_compromised data, assume this
    many records could be exposed.  Conservative mid-range estimate.
    Documented assumption."""

    # ── Loss magnitude — lognormal sigma ──────────────────────────────
    loss_lognormal_sigma: float = 0.75
    """Standard deviation of the log-normal loss-magnitude distribution.
    Controls tail thickness.  0.75 produces a moderately right-skewed
    distribution — most events are near the median cost, but ~5 % of
    events are ≥ 3× the median.  Standard actuarial/FAIR practice range
    is 0.5–1.0.  Configurable."""

    # ── Control aggregation method ────────────────────────────────────
    control_aggregation: str = "multiplicative"
    """How multiple deployed controls' risk_reduction_pct values are
    combined into a single control_resistance for an asset.

    Options:
        "additive_capped"   — sum(pct), capped at 1.0.
                               Simple, optimistic.  May overstate combined
                               effectiveness when controls overlap.
        "multiplicative"    — 1 - product(1 - pct).  Models independent
                               layers of defence.  More conservative.

    Default: "multiplicative" — additive_capped makes EDR (0.85) + MFA (0.95)
    = 1.0 (100% protection), which is unrealistic.  Multiplicative correctly
    models independent layers of defence.

    Example with EDR (0.85) + MFA (0.95):
        additive_capped  → min(1.0, 0.85 + 0.95) = 1.0   (100% reduction)
        multiplicative   → 1 - (1-0.85)*(1-0.95) = 1 - 0.0075 = 0.9925  (99.25%)
    """

    # ── KEV (Known Exploited Vulnerabilities) multiplier ──────────────
    kev_multiplier: float = 1.5
    """Multiplier applied to the annual exploitation probability (p_annual)
    for vulnerabilities flagged as Known Exploited Vulnerabilities (KEV)
    by CISA.  Final value is capped at 1.0.
    Source: CISA KEV catalog — actively exploited in the wild.
    Documented assumption; configurable."""

    # ── EPSS annualisation ────────────────────────────────────────────
    epss_window_days: float = 30.0
    """EPSS scores represent a 30-day exploitation probability.
    Source: FIRST.org EPSS documentation."""

    # ── Beta distribution concentration for vulnerability sampling ────
    vuln_beta_concentration: float = 10.0
    """Concentration parameter for the Beta distribution used to sample
    per-iteration vulnerability values around Vuln_asset.
    Higher values → tighter distribution around the mean.
    α = Vuln_asset × concentration,  β = (1 - Vuln_asset) × concentration.
    10.0 gives moderate spread.  Configurable."""

    # ── Validation ────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Validate configuration on creation."""
        if self.n_simulations < 100:
            raise ValueError(f"n_simulations must be >= 100, got {self.n_simulations}")
        if self.random_seed < 0:
            raise ValueError(f"random_seed must be >= 0, got {self.random_seed}")
        if self.data_timespan_days <= 0:
            raise ValueError(f"data_timespan_days must be > 0, got {self.data_timespan_days}")
        if self.control_aggregation not in ("additive_capped", "multiplicative"):
            raise ValueError(
                f"control_aggregation must be 'additive_capped' or 'multiplicative', "
                f"got '{self.control_aggregation}'"
            )
        # Recompute annualization factor from data_timespan_days
        self.annualization_factor = 365.0 / self.data_timespan_days


# Module-level default instance for convenience
DEFAULT_CONFIG = EngineConfig()
