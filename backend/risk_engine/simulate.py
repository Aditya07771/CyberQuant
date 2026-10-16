import pandas as pd
import numpy as np

from .config import EngineConfig, DEFAULT_CONFIG

class MonteCarloSimulator:
    """Runs Monte Carlo simulations to calculate loss distributions and risk metrics."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        # Use a reproducible random generator
        self.rng = np.random.default_rng(self.config.random_seed)
        # Stores per-asset annual_loss arrays for portfolio-level aggregation
        self.loss_samples: dict = {}
        
    def _generate_lec_points(self, losses: np.ndarray, num_points: int = 100) -> list:
        """
        Generates Loss Exceedance Curve (LEC) points.
        Returns a list of dicts: [{'loss': X, 'probability': Y}, ...]
        """
        if len(losses) == 0:
            return []
            
        # We sample points evenly from the distribution of losses
        sorted_losses = np.sort(losses)
        n_sim = len(sorted_losses)
        
        # We don't need all 20,000 points for a chart, ~100 is enough
        step = max(1, n_sim // num_points)
        
        points = []
        for i in range(0, n_sim, step):
            loss_val = sorted_losses[i]
            # Probability of loss exceeding this value
            prob_exceed = 1.0 - (i / n_sim)
            points.append({"loss": float(loss_val), "probability": float(prob_exceed)})
            
        return points

    def run_simulation(self, row: pd.Series) -> pd.Series:
        """
        Runs Monte Carlo for a single asset and returns risk metrics.
        """
        n_sim = self.config.n_simulations
        
        # 1. Threat Event Frequency (TEF) sampling
        tef_min = row.get("TEF_min", 0.0)
        tef_ml = row.get("TEF_mostlikely", 0.0)
        tef_max = row.get("TEF_max", 0.0)
        
        # Ensure tef bounds are logical (might have floating point inaccuracies)
        if tef_min > tef_ml: tef_min = tef_ml
        if tef_max < tef_ml: tef_max = tef_ml
        
        # If all TEF values are 0 or bounds are identical, sample constant value
        if tef_max == 0.0 or tef_min >= tef_max:
            tef_samples = np.full(n_sim, tef_ml)
        else:
            tef_samples = self.rng.triangular(tef_min, tef_ml, tef_max, size=n_sim)
            
        # 2. Vulnerability sampling (Beta distribution)
        vuln = row.get("Vuln_asset", 0.0)
        if vuln <= 0.0:
            vuln_samples = np.zeros(n_sim)
        elif vuln >= 1.0:
            vuln_samples = np.ones(n_sim)
        else:
            # Beta distribution parameterized around the mean vuln
            concentration = self.config.vuln_beta_concentration
            alpha = vuln * concentration
            beta_param = (1.0 - vuln) * concentration
            vuln_samples = self.rng.beta(alpha, beta_param, size=n_sim)
            
        # 3. Loss Event Frequency (LEF)
        # Expected LEF per simulation draw = TEF * Vuln
        expected_lef = tef_samples * vuln_samples
        # LEF is a count of events, modeled via Poisson
        lef_samples = self.rng.poisson(expected_lef)
        
        # 4. Loss Magnitude & 5. Annual Loss (Compound Poisson-Lognormal)
        mu = row.get("LM_lognormal_mu", 0.0)
        sigma = row.get("LM_lognormal_sigma", 0.75)
        
        if mu <= 0.0:
            annual_loss = np.zeros(n_sim)
        else:
            max_events = int(lef_samples.max()) if lef_samples.max() > 0 else 0
            if max_events > 0:
                # Draw max_events independent loss magnitudes per simulation
                all_draws = self.rng.lognormal(mu, sigma, size=(n_sim, max_events))
                # Mask: only sum draws up to actual event count per simulation
                event_indices = np.arange(max_events)[None, :]  # shape (1, max_events)
                mask = event_indices < lef_samples[:, None]       # shape (n_sim, max_events)
                annual_loss = (all_draws * mask).sum(axis=1)
            else:
                annual_loss = np.zeros(n_sim)
        
        # 6. Summary Risk Metrics
        eal = float(np.mean(annual_loss))
        var95 = float(np.percentile(annual_loss, 95))
        var99 = float(np.percentile(annual_loss, 99))
        
        # CVaR95: mean of losses >= VaR95 (average of worst 5% of years)
        tail_mask = annual_loss >= var95
        cvar95 = float(np.mean(annual_loss[tail_mask])) if tail_mask.any() else var95
        
        lec_points = self._generate_lec_points(annual_loss)
        
        # Store full annual_loss array for portfolio-level aggregation (keyed by asset_id)
        asset_id = row.get("asset_id", None)
        if asset_id is not None:
            self.loss_samples[asset_id] = annual_loss
        
        return pd.Series({
            "EAL_usd": eal,
            "VaR95_usd": var95,
            "VaR99_usd": var99,
            "CVaR95_usd": cvar95,
            "LEC_points": lec_points
        })

    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies Monte Carlo simulation to all assets.
        """
        base_df = df.copy()
        self.loss_samples = {}  # reset for fresh run
        
        # Run simulation
        sim_cols = base_df.apply(self.run_simulation, axis=1)
        
        # Concatenate results
        res_df = pd.concat([base_df, sim_cols], axis=1)
        return res_df
