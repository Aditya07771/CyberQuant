import pandas as pd
from .investment_optimizer import optimize_investments

def compute_frontier(scenarios_df: pd.DataFrame, n_points: int = 15, one_control_per_asset: bool = True) -> dict:
    """Run the ILP optimizer at multiple budget levels to build the efficient frontier."""
    max_cost = float(scenarios_df["cost_usd"].sum())
    if max_cost <= 0:
        return {"frontier_points": [], "knee_point_index": 0}
    
    # Generate budget points from 2% to 100% of max possible cost
    fractions = [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]
    budget_points = [max_cost * f for f in fractions[:n_points]]
    
    frontier_points = []
    for budget in budget_points:
        try:
            result = optimize_investments(scenarios_df, budget_usd=budget, one_control_per_asset=one_control_per_asset)
            frontier_points.append({
                "budget_usd": round(budget, 2),
                "risk_reduction_usd": result["total_risk_reduction_usd"],
                "residual_eal_usd": result["residual_eal_usd"],
                "n_actions": result["n_actions_selected"],
                "utilization_pct": result["budget_utilization_pct"],
                "greedy_risk_reduction_usd": result["greedy_comparison"]["total_risk_reduction_usd"],
            })
        except Exception:
            continue
    
    # Find knee point using maximum curvature approximation
    knee_idx = _find_knee_point(frontier_points)
    
    return {
        "frontier_points": frontier_points,
        "knee_point_index": knee_idx,
        "max_possible_budget": max_cost,
    }

def _find_knee_point(points: list) -> int:
    """Find the knee/elbow point where diminishing returns begin.
    Uses the point of maximum distance from the line connecting first and last points."""
    if len(points) < 3:
        return 0
    
    import numpy as np
    x = np.array([p["budget_usd"] for p in points])
    y = np.array([p["risk_reduction_usd"] for p in points])
    
    # Normalize
    x_norm = (x - x[0]) / (x[-1] - x[0]) if x[-1] != x[0] else np.zeros_like(x)
    y_norm = (y - y[0]) / (y[-1] - y[0]) if y[-1] != y[0] else np.zeros_like(y)
    
    # Distance from line connecting first to last point
    line_vec = np.array([x_norm[-1] - x_norm[0], y_norm[-1] - y_norm[0]])
    line_len = np.sqrt(line_vec[0]**2 + line_vec[1]**2)
    if line_len == 0:
        return 0
    line_unit = line_vec / line_len
    
    distances = []
    for i in range(len(points)):
        point_vec = np.array([x_norm[i] - x_norm[0], y_norm[i] - y_norm[0]])
        proj = np.dot(point_vec, line_unit)
        proj_point = line_unit * proj
        dist = np.sqrt(((point_vec - proj_point)**2).sum())
        distances.append(dist)
    
    return int(np.argmax(distances))
