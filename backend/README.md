# Cyber Risk Quantification Platform

An AI-powered, **FAIR-aligned** Cyber Risk Quantification platform built for SIH Problem 
Statement 26105. It converts raw technical cybersecurity telemetry (vulnerabilities, threat 
events, deployed controls) into **financial risk metrics** — Expected Annual Loss (EAL), 
Value at Risk (VaR95/VaR99), and Return on Security Investment (ROSI) — so that CISOs, risk 
officers, and executive leadership can make data-driven, budget-constrained security 
investment decisions instead of relying on qualitative "Low/Medium/High" risk ratings.

---

## What's New
- **CVaR 95 (Expected Shortfall)**: Quantifies average tail loss across the worst 5% of simulated years for each asset and the enterprise portfolio.
- **Real Portfolio Distribution**: Element-wise combined loss distribution and empirical LEC points saved to `outputs/org_lec.json`.
- **KEV Multiplier**: 1.5× likelihood multiplier for CISA Known Exploited Vulnerabilities, with `multiplicative` control resistance as default.
- **Cost per Incident Breakdown**: Itemized per-event exposure across downtime, incident response, data breach, and regulatory penalties.
- **EAL Driver Analysis (`drivers.py`)**: Counterfactual explainability isolating risk deltas for worst CVE, KEV status, controls, and TEF.
- **Standard ROSI Formula**: Evaluates net return as `ROSI = (Risk_Reduction_usd − cost_usd) / cost_usd`.
- **USD ⇄ INR Currency Toggle**: Live display switcher with Indian numbering notation (Cr / L / ₹) and configurable exchange rate.

---

## Dataset (`data/`)

A simulated, relational dataset representing the technical telemetry and business context 
required to model cyber risk financially — 5 interconnected CSV files.

### 1. `assets.csv` — Business Context
`asset_id, hostname, business_unit, criticality (1-5), data_sensitivity_tier, 
financial_value_usd, downtime_cost_per_hour_usd, regulatory_penalty_potential_usd, os`
Defines the intrinsic value and potential loss magnitude (in USD) if an asset is compromised.

### 2. `vulnerabilities.csv` — Technical Weaknesses
`vuln_id, asset_id (FK), cve_id, cvss_score, epss_score, severity, status, discovery_date`
Feeds the Likelihood and Vulnerability-factor calculations. `epss_score` (FIRST.org's 
Exploit Prediction Scoring System) gives a real, externally-maintained probability of 
exploitation — not a guess.

### 3. `threat_events.csv` — Historical Incident Data
`event_id, timestamp, asset_id (FK), mitre_technique_id, description, severity, source_ip, 
action_taken, downtime_hours_caused, records_compromised`
Simulated SIEM-style alert log. Provides the empirical basis for Threat Event Frequency and 
for the downtime/records-exposed inputs to Loss Magnitude.

### 4. `controls.csv` — Mitigation Catalog
`control_id, name, risk_reduction_pct, cost_usd`
The catalog of available security defenses (MFA, EDR, Network Segmentation, Patching) with 
their cost and effectiveness — the cost-benefit inputs for the optimization module.

### 5. `asset_controls.csv` — Deployed Defenses
`mapping_id, asset_id (FK), control_id (FK), status, deployment_date`
Maps which controls are currently active on which assets — required to compute *residual* 
risk (risk after existing defenses), not raw/unmitigated risk.

### Regenerating the Dataset
```bash
python scripts/generate_dataset.py
```

---

## Risk Calculation Engine (`risk_engine/`)

The engine implements a **FAIR-aligned, Monte Carlo-based** methodology — every formula is 
traceable to either the source data or a named external standard, not an invented shortcut. 
This traceability is itself a design goal: RBI/SEBI-style frameworks require auditability, 
and being able to answer "where did this number come from?" for any output is what makes the 
model defensible.

### Pipeline Stages

**1. Ingestion & Normalization (`ingest.py`)**
Joins the 5 raw CSVs into a single `asset_risk_base` table keyed on `asset_id` — one row per 
asset with aggregated vulnerability lists, event counts, and active controls. Every 
downstream calculation reads from this table, never from raw CSVs again.

**2. Likelihood (`likelihood.py`)**
- **EPSS annualization**: EPSS scores a 30-day exploitation window, but FAIR risk is 
  expressed annually, so naive multiplication (`EPSS × 12`) is mathematically wrong (it can 
  exceed 1.0). The engine uses the correct survival-probability formula:
  `P_annual = 1 - (1 - EPSS_30day)^(365/30)`
- **CVSS normalization**: `severity_norm = cvss_score / 10`, kept as a separate 0–1 
  dimension from probability, per the FAIR principle of not blending "how likely" with "how 
  bad" into one fake number.
- **Vulnerability factor**: combines annualized probability (multiplied by `kev_multiplier` if flagged on CISA KEV), severity, and current control 
  resistance per CVE, then takes the **maximum across an asset's CVEs** (not the average) — 
  because an attacker only needs the single weakest link:
  ```
  control_resistance = 1 - product(1 - pct)   # multiplicative, per config.py
  vuln_per_cve = p_annual_exploit * severity_norm * (1 - control_resistance)
  Vuln_asset = max(vuln_per_cve for cve in asset.vuln_list)
  ```

**3. Threat Event Frequency — TEF (`frequency.py`)**
Derived empirically from `threat_events.csv` rather than assumed. Modeled as a **triangular 
distribution** (min/most-likely/max), not a single number, to preserve real-world uncertainty 
for the Monte Carlo stage. If an asset has fewer than 3 historical events (too sparse to be 
statistically meaningful), its business unit's aggregate event-rate distribution is borrowed 
instead — a documented assumption, not a silent gap-fill.

**4. Loss Magnitude (`loss_magnitude.py`)**
Two components, calibrated separately for defensibility:
- **Primary Loss** (internal, defensible from your own data): 
  `downtime_cost_per_hour_usd × downtime_hours + IR_flat_cost`
- **Secondary Loss** (external, benchmark-calibrated): 
  `sensitivity_multiplier[data_sensitivity_tier] × per_record_cost × records_compromised`, 
  where `per_record_cost` is anchored to a named, dated external breach-cost benchmark 
  (e.g., IBM/Ponemon Cost of a Data Breach Report).
- Combined into a **lognormal distribution** (`sigma=0.75`, configurable) rather than a point 
  estimate — real breach costs are right-skewed (many small incidents, occasional 
  catastrophic ones), which a normal distribution would understate.

**5. Monte Carlo Simulation (`simulate.py`)**
Vectorized (NumPy) simulation combining TEF and Loss Magnitude distributions per asset:
```python
tef_sample  = triangular(TEF_min, TEF_ml, TEF_max)
vuln_sample = beta(a, b)                      # mean ≈ Vuln_asset
lef_sample  = poisson(tef_sample * vuln_sample)   # Loss Event Frequency
annual_loss = lef_sample * loss_magnitude_sample  # per iteration, vectorized
```
Run across thousands of iterations per asset, producing a full **annual loss distribution** — 
not a single "risk score." Every summary metric below is derived from this distribution.

**6. Aggregation & Summary Metrics (`aggregate.py`)**
- **EAL** (mean of the distribution) — "typical year" exposure.
- **VaR95 / VaR99** (95th/99th percentile) — "bad year" exposure. Both are reported together, 
  since EAL alone hides tail risk and VaR alone hides the common case.
- **CVaR95** (mean of the worst 5% tail losses) — Expected Shortfall measuring catastrophe depth.
- Rolled up to **business-unit** and **organization** level. The portfolio-wide distribution is built by adding per-asset simulated losses element-wise for each simulated year, while summed upper-bound fields are retained for transparency.
- `priority_score = EAL × (criticality / 5)` — used only for ranking/prioritization display, 
  never baked into the EAL dollar figure itself.

**7. Control Scenario Simulation (`control_scenarios.py`)**
For every candidate control not already deployed on an asset, the engine estimates
risk reduction using the vulnerability ratio shortcut rather than full re-simulation:
```
EAL_before = baseline_EAL
EAL_after  = EAL_before × (new_vuln / old_vuln)
Risk_Reduction_usd = EAL_before - EAL_after
ROSI = (Risk_Reduction_usd - cost_usd) / cost_usd
```
This vulnerability ratio shortcut avoids re-running the 20,000-iteration Monte Carlo
simulation for every scenario while preserving directional accuracy and proportionality.

### Configuration (`config.py`)
All tunable assumptions live here — sensitivity multipliers, lognormal sigma, control 
resistance mode (`multiplicative`), KEV multiplier (1.5), the "sparse history" threshold, VaR percentiles, and 
Monte Carlo iteration count — so they can be adjusted without touching pipeline logic.

### Running the Pipeline
```bash
python -m risk_engine.pipeline
```
This runs the full Monte Carlo simulation and writes results to `outputs/`.

---

## Outputs (`outputs/`)

The pipeline produces parquet and JSON outputs:

| File | Contents |
|---|---|
| `asset_risk_summary.parquet` | Per-asset EAL, VaR95, VaR99, CVaR95, EAL_simple_usd, loss breakdowns, priority_score |
| `business_unit_risk_summary.parquet` | Per-business-unit aggregated EAL/VaR95 and top risk contributors |
| `org_risk_summary.parquet` | Organization-wide EAL, VaR95, VaR99, CVaR95 (real distribution and upper-bound) |
| `control_scenario_results.parquet` | Every candidate control × asset pair: cost, EAL_before, EAL_after, Risk_Reduction_usd, ROSI |
| `org_lec.json` | Empirical Loss Exceedance Curve points (~100 points) for the organization distribution |

`control_scenario_results.parquet` is the direct input to the **Investment 
Optimization module** and powers "what-if" queries in the interface — 
no further transformation is needed.

---

## API (`api/`)

A FastAPI layer exposes the risk metrics for the dashboard and other consumers.

### Start the server
```bash
uvicorn api.main:app --reload
```
Interactive docs available at `http://localhost:8000/docs`.

### Key Endpoints

**`GET /risk/assets`** — Returns risk metrics for all assets.

**`GET /risk/assets/{asset_id}`** — Returns detailed risk metrics, loss breakdown, and LEC for an asset.

**`GET /risk/assets/{asset_id}/drivers`** — Returns counterfactual EAL sensitivity drivers.

**`GET /risk/business-units`** — Returns aggregated risk metrics per business unit.

**`GET /risk/organization`** — Returns enterprise-level metrics including CVaR95.

**`GET /risk/portfolio-lec`** — Returns empirical portfolio-wide loss exceedance curve data.

**`GET /controls/roi`** — Returns controls ranked by overall ROSI.

**`GET /controls/optimize`** — Runs exact Knapsack ILP investment optimization under a budget limit.

---

## Key Modeling Assumptions (FAIR-aligned)

All assumptions and tunables are managed in `risk_engine/config.py`.

1. **EPSS Annualization** — probability annualized using the standard survival formula 
   `1 - (1 - epss_30)**(365/30)`, not naive multiplication.
2. **CVSS Normalization** — divided by 10.0 to act as a severity coefficient, kept separate 
   from likelihood.
3. **Control Resistance** — handled as `multiplicative` (1 - product(1 - pct), modeling independent defense-in-depth layers; configurable to `additive_capped`).
4. **Threat Event Frequency (TEF)** — modeled via a triangular distribution; if an asset has 
   fewer than 3 historical events, the business-unit aggregate distribution is used instead.
5. **Loss Magnitude (LM)** — sum of Primary Loss (downtime × cost + IR flat cost) and 
   Secondary Loss (records × per-record cost + regulatory penalty), modeled as a lognormal 
   distribution (`sigma=0.75`).
6. **Independence** — EAL is summed linearly across assets (documented upper-bound 
   approximation); portfolio tail metrics (VaR95/VaR99/CVaR95) are derived from the element-wise combined Monte Carlo distribution.
7. **Control Scenarios** — candidate controls are evaluated using the vulnerability ratio shortcut `EAL_after = EAL_before × (new_vuln / old_vuln)`, with standard ROSI = `(Risk_Reduction - cost) / cost`.

### Credibility / Standards Backing

| Model Component | External Standard/Source |
|---|---|
| Vulnerability probability | EPSS (FIRST.org) |
| Technical severity | CVSS (FIRST.org / NIST) |
| Overall model structure | FAIR / Open FAIR (The Open Group standard) |
| Loss magnitude calibration | Named, dated external breach-cost benchmark (e.g. IBM/Ponemon) |
| Simulation methodology | Monte Carlo with triangular/beta/lognormal distributions — standard actuarial/FAIR practice |
| Independence/correlation limitation | Explicitly documented as a simplification, not hidden |

Every number surfaced by the API or dashboard is traceable to one of the rows above — stated 
explicitly in the pitch/demo, this traceability is what makes the model defensible under 
judge questioning rather than appearing as a black box.

---

## Installation

```bash
pip install -r requirements.txt
```

## Running Everything

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the end-to-end risk simulation pipeline
python -m risk_engine.pipeline
# → runs the Monte Carlo simulations and writes results into outputs/

# 3. Launch the REST API server
uvicorn api.main:app --reload
# → interactive docs at http://localhost:8000/docs

# 4. Run the test suite
python -m pytest tests/ -v
```

## Tests (`tests/`)

A Pytest suite covers every engine module (`ingest`, `likelihood`, `frequency`, 
`loss_magnitude`, `simulate`, `control_scenarios`, `drivers`), validating the correctness of each 
transformation independently before it feeds the next pipeline stage.

---
