import logging
from pathlib import Path
import pandas as pd

import json
from .config import EngineConfig, DEFAULT_CONFIG
from .ingest import DataIngestor
from .likelihood import LikelihoodModel
from .frequency import FrequencyModel
from .loss_magnitude import LossMagnitudeModel
from .simulate import MonteCarloSimulator
from .aggregate import RiskAggregator
from .control_scenarios import ControlScenarios
from .predictor import VulnerabilityPredictor
from .trend_generator import generate_risk_trend
from .threat_forecaster import ThreatSequenceForecaster

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class RiskPipeline:
    """End-to-end orchestration of the Risk Quantification Engine."""
    
    def __init__(self, config: EngineConfig = DEFAULT_CONFIG):
        self.config = config
        
    def run_all(self):
        """Runs the complete FAIR-aligned risk quantification pipeline."""
        logger.info("Starting Cyber Risk Quantification Pipeline...")
        
        # 1. Ingest
        logger.info("Phase B: Ingesting and normalizing data...")
        ingestor = DataIngestor(self.config)
        raw_data = ingestor.load_data()
        base_df = ingestor.build_asset_risk_base(raw_data)
        
        # 2. Likelihood
        logger.info("Phase C: Calculating vulnerabilities (EPSS/CVSS)...")
        likelihood = LikelihoodModel(self.config)
        df = likelihood.apply_to_dataframe(base_df)
        
        # 3. Frequency
        logger.info("Phase D: Estimating Threat Event Frequencies...")
        frequency = FrequencyModel(self.config)
        df = frequency.apply_to_dataframe(df)
        
        # 4. Loss Magnitude
        logger.info("Phase E: Calculating Loss Magnitudes...")
        loss_mag = LossMagnitudeModel(self.config)
        df = loss_mag.apply_to_dataframe(df)

        # 4b. EAL_simple_usd = TEF_mostlikely * Vuln_asset * LM_mean_usd
        if all(c in df.columns for c in ["TEF_mostlikely", "Vuln_asset", "LM_mean_usd"]):
            df["EAL_simple_usd"] = df["TEF_mostlikely"] * df["Vuln_asset"] * df["LM_mean_usd"]
        
        # 5. Monte Carlo Simulation
        logger.info(f"Phase F: Running Monte Carlo Simulation ({self.config.n_simulations} iterations per asset)...")
        simulator = MonteCarloSimulator(self.config)
        df = simulator.apply_to_dataframe(df)
        
        # 6. Aggregation (pass simulator so portfolio loss distribution is computed from real samples)
        logger.info("Phase G: Aggregating risk metrics...")
        aggregator = RiskAggregator(self.config)
        aggregates = aggregator.aggregate(df, simulator=simulator)
        
        # 7. Control Scenarios
        logger.info("Phase H: Evaluating Control Scenarios and ROSI...")
        scenarios = ControlScenarios(self.config)
        controls_df = raw_data["controls"]
        scenario_results = scenarios.evaluate_scenarios(df, controls_df)
        
        out_dir = self.config.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Phase I: ML Vulnerability Exploitation Prediction
        logger.info("Phase I: Training vulnerability exploitation predictor...")
        predictor = VulnerabilityPredictor()
        features, labels = predictor.prepare_features(raw_data)
        if not features.empty:
            metrics = predictor.train(features, labels)
            logger.info(f"Predictor trained. Metrics: {metrics}")
            predictions = predictor.predict(features)
            
            # Create a dataframe for predictions. We need asset_id and cve_id if possible.
            vulns = raw_data.get("vulnerabilities")
            if not isinstance(vulns, pd.DataFrame):
                vulns = pd.DataFrame(vulns)
            
            if not vulns.empty:
                vuln_preds = vulns.copy()
                # Assuming order is preserved, which prepare_features does by merging
                # Actually prepare_features merges, which might reorder. Let's just store features along with probability.
                # Since prepare_features uses vulns.merge, let's just do that to get the same length and order:
                assets = raw_data.get("assets", pd.DataFrame())
                if not isinstance(assets, pd.DataFrame):
                    assets = pd.DataFrame(assets)
                if not assets.empty:
                    merged = vulns.merge(assets, on="asset_id", suffixes=("", "_asset"))
                    merged["exploit_probability_rf"] = predictions["random_forest"]
                    merged["exploit_probability_xgb"] = predictions["xgboost"]
                    # For backward compatibility with UI if it only expects one:
                    merged["exploit_probability"] = predictions["random_forest"] 
                    merged.to_parquet(out_dir / "vuln_predictions.parquet", index=False)
                else:
                    vuln_preds["exploit_probability_rf"] = predictions["random_forest"]
                    vuln_preds["exploit_probability_xgb"] = predictions["xgboost"]
                    vuln_preds["exploit_probability"] = predictions["random_forest"]
                    vuln_preds.to_parquet(out_dir / "vuln_predictions.parquet", index=False)
        else:
            logger.info("No vulnerabilities found, skipping predictor.")

        # Phase J: Generate Risk Trend History
        logger.info("Phase J: Generating risk trend analysis...")
        trend_df = generate_risk_trend(aggregates["org_risk_summary"], raw_data, self.config)
        trend_df.to_parquet(out_dir / "risk_trend.parquet", index=False)
        
        # Phase K: Sequential LSTM Threat Event & Attack Sequence Forecasting
        logger.info("Phase K: Training sequential LSTM threat event forecaster...")
        threat_events_data = raw_data.get("threat_events")
        if not isinstance(threat_events_data, pd.DataFrame):
            threat_events_data = pd.DataFrame(threat_events_data)
        
        if not threat_events_data.empty:
            forecaster = ThreatSequenceForecaster(window_size=7, forecast_horizon=14)
            forecast_result = forecaster.train_and_forecast(threat_events_data)
            forecast_path = out_dir / "threat_forecast.json"
            with open(forecast_path, "w") as f:
                json.dump(forecast_result, f, indent=2)
            logger.info("LSTM threat forecasting completed and saved.")
        else:
            logger.info("No threat events telemetry found, skipping LSTM forecaster.")

        # 8. Save Outputs
        logger.info("Saving core results to parquet...")
        
        # Drop complex structures for parquet serialization where necessary
        asset_summary = aggregates["asset_risk_summary"].copy()
        asset_summary["LEC_points"] = asset_summary["LEC_points"].apply(list)
        
        asset_summary.to_parquet(out_dir / "asset_risk_summary.parquet", index=False)
        aggregates["business_unit_risk_summary"].to_parquet(out_dir / "business_unit_risk_summary.parquet", index=False)
        aggregates["org_risk_summary"].to_parquet(out_dir / "org_risk_summary.parquet", index=False)
        scenario_results.to_parquet(out_dir / "control_scenario_results.parquet", index=False)

        # Save org LEC points for real portfolio distribution
        org_lec_points = aggregates.get("org_lec_points", [])
        if org_lec_points:
            with open(out_dir / "org_lec.json", "w") as f:
                json.dump(org_lec_points, f, indent=2)
            logger.info("Saved org_lec.json with real portfolio loss distribution.")
        
        # Precompute efficient frontier cache for sub-millisecond API responses
        try:
            from .frontier import compute_frontier
            frontier_data = compute_frontier(scenario_results)
            with open(out_dir / "frontier_cache.json", "w") as f:
                json.dump(frontier_data, f, indent=2)
            logger.info("Precomputed efficient frontier cache saved.")
        except Exception as e:
            logger.warning(f"Could not precompute frontier cache: {e}")
        
        # For full traceability, optionally save the complete df
        # df.to_parquet(out_dir / "full_simulation_base.parquet", index=False)
        
        logger.info("Pipeline completed successfully!")
        
if __name__ == "__main__":
    pipeline = RiskPipeline()
    pipeline.run_all()
