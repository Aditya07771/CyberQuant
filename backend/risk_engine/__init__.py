"""
Cyber Risk Quantification Engine
================================

A FAIR-aligned risk quantification engine that converts technical cybersecurity
telemetry into financial cyber risk metrics (EAL, VaR95, VaR99, LEC).

Modules:
    config          — All configurable parameters, assumptions, and constants
    ingest          — CSV loading, validation, and asset_risk_base construction
    likelihood      — EPSS annualization, CVSS normalization, vulnerability factor
    frequency       — Threat Event Frequency (TEF) estimation
    loss_magnitude  — Primary/Secondary loss and lognormal calibration
    simulate        — Vectorized Monte Carlo simulation engine
    aggregate       — Asset → BU → Org aggregation and LEC generation
    control_scenarios — What-if control simulation and ROSI calculation
    pipeline        — End-to-end orchestrator (run_all)
"""

__version__ = "1.0.0"
