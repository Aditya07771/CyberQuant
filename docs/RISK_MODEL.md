# Risk Model Requirements

## Purpose and semantics
Return quantitative annual financial exposure and uncertainty, not a severity score disguised as money. Keep one engine built on existing `likelihood.py`, `frequency.py`, `loss_magnitude.py`, `simulate.py`, `aggregate.py` and `control_scenarios.py`. Label all assumptions, source evidence, model version and data-quality limits.

## Per-asset scenario model
For asset `i` and scenario `s`, separate:
- Threat Event Frequency (`TEF`): events per year, estimated from observed telemetry over an explicit observation window; use a documented hierarchical/business-unit prior when asset evidence is sparse.
- Probability of loss given a threat event: scenario/exposure/control dependent, in `[0,1]` and calibrated where labels exist.
- Loss Event Frequency (`LEF`): expected successful loss events/year. A Poisson count with rate `TEF × P(loss | event)` is allowed only when assumptions fit; retain uncertainty in both terms.
- Loss Magnitude: distribution over non-negative amounts with explicit components and conditionality.
- Annual loss: sum of simulated event losses in a simulated year. EAL is its sample mean.

### Likelihood inputs
- EPSS is a 30-day exploitation-probability signal, not a probability of this asset suffering a breach. If annualizing as `1-(1-p30)^(365/30)`, label the stationary/independent-window assumption, cap numerical results to `[0,1]`, and calibrate against observed data. Do not multiply `CVSS/10` into exploit probability without a validated model.
- Preserve CVSS version/vector/score as technical severity/impact evidence. Use business impact, internet/external exposure, reachable attack paths, asset criticality and control applicability separately.
- CISA KEV is evidence that a vulnerability is known exploited in the wild, not proof this tenant's asset was exploited. Use it to prioritize/condition the scenario with a versioned, sensitivity-tested rule—not an undocumented arbitrary multiplier.
- Keep raw signals, transformed values, rationale, source timestamp, missingness and model version in results.

### Controls
- A percentage in a control catalog is an assumption until supported by evidence/measurement. Model controls by category and affected risk component where possible: prevention may reduce event success; detection/response may reduce dwell time or loss magnitude; recovery may reduce outage duration.
- Avoid additive-capped stacking that can produce 100% risk reduction. Do not allow a few controls to make modeled residual risk exactly zero. Model overlaps/dependencies and show uncertainty. Validate scenarios with monotonicity properties where a control is correctly specified.

## Loss magnitude
Keep itemized components and avoid double counting:
- Primary/direct: downtime cost × outage hours, response/forensics, containment, restore/rebuild and remediation.
- Conditional secondary: notification/support, legal/claims, contractual loss, regulatory exposure scenarios and reputation-driven lost margin where evidenced.
- Separate direct revenue loss from downstream reputation loss; do not count the same outage/revenue in multiple components.
- For each component retain currency, source, date, low/most-likely/high or quantiles, confidence, owner and assumption/actual status. Use organization-specific values first and sourced assumptions only as labeled fallback.
- Fit the chosen distribution to explicitly defined quantiles. If low/high are stated as q05/q95 for lognormal data, use consistent normal quantiles; if inputs are q10/q90 use the corresponding 1.28155 z-score, not 1.64485. For min/mode/max, use a documented triangular/lognormal fitting method. Test it numerically.
- Apply insurance only to covered components after deductible/limit/exclusions; never subtract a full policy limit indiscriminately.

## Monte Carlo and metrics
- Seed runs for reproducibility and save seed, iteration count, config/model code version, source dataset version and frozen external data references.
- Per asset calculate EAL, VaR95/VaR99, ES95/ES99 (average tail loss at the stated quantile), distribution/LEC and loss component summaries. VaR95 is the 95th percentile—not a 95% probability of exactly that loss.
- Portfolio simulation must combine each asset's loss samples per iteration and include explicit common-cause scenarios for shared identity, cloud, network or ransomware events when supported. Compute portfolio quantiles from combined samples. Summing asset EALs is acceptable under a well-defined additive loss model; summing asset VaRs is not portfolio VaR.
- If dependence cannot be estimated, publish the independence assumption and sensitivity scenarios; do not imply observed correlation. Any upper-bound/approximation must be labeled.
- Return uncertainty/data-sufficiency labels; never replace missing threat/loss data with zero-risk outputs.

## Optimization and comparison
- Calculate marginal control impact using comparable simulation scenarios with common random numbers where practical. Include cost, deployment dependencies, policy-required controls, controls already deployed and budget constraints.
- `ROSI = (risk_reduction_usd - cost_usd) / cost_usd` only when cost is positive and benefit/cost horizons are aligned. Show NPV/discounting assumptions when comparing multi-year costs and benefits.
- Retain ILP and greedy baseline results, report optimality/status and solver errors, and expose each selection's estimated risk reduction, marginal cost, constraints and residual portfolio risk.

## Validation requirements
Property tests: probabilities `[0,1]`, nonnegative losses, `ES95 >= VaR95 >= 0`, `ES99 >= VaR99`, monotonic quantiles, deterministic seeded output and correct zero-event behavior. Calibration tests must compare outputs with fixture data / baselines; statistical correctness tests alone do not prove real-world predictive validity.
