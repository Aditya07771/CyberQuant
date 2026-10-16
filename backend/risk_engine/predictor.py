import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_validate
from typing import Tuple, Dict, Any, List

class VulnerabilityPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            xgb_fallback = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
        except Exception:
            xgb_fallback = RandomForestClassifier(n_estimators=100, random_state=42)
        self.models = {
            "random_forest": self.model,
            "xgboost": xgb_fallback
        }
        self.feature_names = []
        self.is_trained = False
        self.metrics = {}
        
    def prepare_features(self, raw_data: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.Series]:
        """Extract features and target labels from raw data."""
        # Convert inputs to DataFrames if they aren't already
        vulns = raw_data.get("vulnerabilities", [])
        if not isinstance(vulns, pd.DataFrame):
            vulns = pd.DataFrame(vulns)
            
        assets = raw_data.get("assets", [])
        if not isinstance(assets, pd.DataFrame):
            assets = pd.DataFrame(assets)
            
        threat_events = raw_data.get("threat_events", [])
        if not isinstance(threat_events, pd.DataFrame):
            threat_events = pd.DataFrame(threat_events)
            
        controls = raw_data.get("asset_controls", [])
        if not isinstance(controls, pd.DataFrame):
            controls = pd.DataFrame(controls)
            
        if vulns.empty:
            return pd.DataFrame(), pd.Series()
            
        # Merge vulnerability with asset info
        df = vulns.merge(assets, on="asset_id", suffixes=("", "_asset"))
        
        # Calculate epss_annual
        df["epss_score"] = df["epss_score"].fillna(0.01).astype(float)
        df["epss_annual"] = 1 - (1 - df["epss_score"])**(365/30)
        
        # Calculate asset_criticality
        df["asset_criticality"] = df["criticality"].fillna(3).astype(float)
        
        # Calculate data_sensitivity_numeric
        sensitivity_map = {"Public": 1, "Internal": 2, "Confidential": 3, "Restricted": 4}
        df["data_sensitivity_numeric"] = df["data_sensitivity_tier"].map(sensitivity_map).fillna(2.0).astype(float)
        
        # Calculate control_coverage
        control_coverage = {}
        if not controls.empty:
            control_defs = raw_data.get("controls", [])
            if not isinstance(control_defs, pd.DataFrame):
                control_defs = pd.DataFrame(control_defs)
            
            if not control_defs.empty and "control_id" in controls.columns:
                merged_ctrls = controls.merge(control_defs, on="control_id", how="left")
                if "risk_reduction_pct" in merged_ctrls.columns:
                    grouped = merged_ctrls.groupby("asset_id")["risk_reduction_pct"].sum()
                    control_coverage = grouped.to_dict()
        df["control_coverage"] = df["asset_id"].map(control_coverage).fillna(0.0)
        df["control_coverage"] = df["control_coverage"].clip(0, 1.0)
        
        # Calculate vuln_age_days
        now = pd.Timestamp.now(tz='UTC').tz_localize(None)
        if "discovery_date" in df.columns:
            disc_date = pd.to_datetime(df["discovery_date"]).dt.tz_localize(None)
            df["vuln_age_days"] = (now - disc_date).dt.days.fillna(0.0).astype(float)
        else:
            df["vuln_age_days"] = 30.0
            
        # Calculate asset_event_count
        event_counts = {}
        if not threat_events.empty and "asset_id" in threat_events.columns:
            event_counts = threat_events.groupby("asset_id").size().to_dict()
        df["asset_event_count"] = df["asset_id"].map(event_counts).fillna(0).astype(float)
        
        # Calculate asset_financial_value_log
        df["asset_financial_value_log"] = np.log1p(df["financial_value_usd"].fillna(0).astype(float))
        
        # Calculate has_open_critical
        if "severity" in vulns.columns:
            critical_vulns = vulns[vulns["severity"].astype(str).str.lower() == "critical"]
        elif "cvss_score" in vulns.columns:
            critical_vulns = vulns[vulns["cvss_score"].astype(float) >= 9.0]
        else:
            critical_vulns = pd.DataFrame()

        critical_counts = critical_vulns.groupby("asset_id").size().to_dict() if not critical_vulns.empty and "asset_id" in critical_vulns.columns else {}
        df["has_open_critical"] = df["asset_id"].map(lambda aid: 1.0 if critical_counts.get(aid, 0) > 0 else 0.0)
        
        # Prepare target label
        allowed_assets = set()
        status_col = "action_taken" if "action_taken" in threat_events.columns else ("status" if "status" in threat_events.columns else None)
        if not threat_events.empty and status_col and "asset_id" in threat_events.columns:
            allowed_events = threat_events[threat_events[status_col].astype(str).str.lower() == "allowed"]
            allowed_assets = set(allowed_events["asset_id"])
            
        df["has_allowed_events"] = df["asset_id"].apply(lambda x: 1 if x in allowed_assets else 0)
        df["cvss_score"] = df["cvss_score"].fillna(5.0).astype(float) if "cvss_score" in df.columns else 5.0
        
        exploit_prob = df["epss_annual"] * (df["cvss_score"] / 10.0) * df["has_allowed_events"].apply(lambda x: 1.0 if x else 0.3)
        threshold = exploit_prob.quantile(0.7) if not exploit_prob.empty else 0.5
        y = (exploit_prob > threshold).astype(int)
        
        features = [
            "cvss_score", "epss_score", "epss_annual", "asset_criticality",
            "data_sensitivity_numeric", "control_coverage", "vuln_age_days",
            "asset_event_count", "asset_financial_value_log", "has_open_critical"
        ]
        
        X = df[features].fillna(0.0)
        self.feature_names = features
        return X, y
        
    def train(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        if len(X) < 5 or len(y.unique()) < 2:
            try:
                self.models["random_forest"].fit(X, y)
                self.models["xgboost"].fit(X, y)
            except Exception:
                pass
            self.is_trained = True
            return {"error": "Not enough data for cross-validation"}
            
        try:
            import xgboost as xgb
            xgb_model = xgb.XGBClassifier(n_estimators=100, learning_rate=0.1, random_state=42, eval_metric="logloss")
        except (ImportError, Exception):
            from sklearn.ensemble import GradientBoostingClassifier
            xgb_model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)

        self.models = {
            "random_forest": self.model,
            "xgboost": xgb_model
        }
        
        self.metrics = {}
        for name, model in self.models.items():
            cv_results = cross_validate(model, X, y, cv=5, scoring=['f1', 'precision', 'recall'])
            model.fit(X, y)
            
            importances = model.feature_importances_
            sorted_indices = np.argsort(importances)[::-1]
            feat_imp = [(self.feature_names[i], float(importances[i])) for i in sorted_indices]
            
            self.metrics[name] = {
                "cv_f1_scores": cv_results['test_f1'].tolist(),
                "mean_f1": float(np.mean(cv_results['test_f1'])),
                "precision": float(np.mean(cv_results['test_precision'])),
                "recall": float(np.mean(cv_results['test_recall'])),
                "feature_importance": feat_imp
            }
            
        self.is_trained = True
        return self.metrics
        
    def predict(self, X: pd.DataFrame) -> dict:
        if not self.is_trained:
            raise ValueError("Model not trained")
        # Ensure features are in order
        X_aligned = X[self.feature_names].fillna(0.0) if self.feature_names else X.fillna(0.0)
        n_samples = len(X_aligned)
        
        preds = {}
        for name, model in self.models.items():
            try:
                probs = model.predict_proba(X_aligned)
                if probs.shape[1] > 1:
                    preds[name] = probs[:, 1]
                else:
                    preds[name] = probs[:, 0]
            except Exception:
                preds[name] = np.full(n_samples, 0.5)
        return preds
        
    def get_feature_importance(self) -> List[Tuple[str, float]]:
        # For backwards compatibility, return RF
        return self.metrics.get("random_forest", {}).get("feature_importance", [])
