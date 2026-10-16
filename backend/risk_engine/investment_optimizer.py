from __future__ import annotations

import pandas as pd
import pulp


def optimize_investments(
    scenarios: pd.DataFrame,
    budget_usd: float,
    one_control_per_asset: bool = True,
) -> dict:
    """
    Select the subset of candidate (asset, control) actions that maximizes
    total Risk_Reduction_usd subject to a total cost cap.

    Parameters
    ----------
    scenarios : DataFrame
        Must have columns: control_id, control_name (or name), asset_id,
        cost_usd, EAL_before, EAL_after, Risk_Reduction_usd, ROSI.
        One row per candidate action (i.e. control_scenario_results.parquet).
        Each row's Risk_Reduction_usd is computed independently against the
        current baseline (see risk_engine's control_scenarios.py) — it does
        NOT account for other candidate controls also being added to the
        same asset.
    budget_usd : float
        Total available budget.
    one_control_per_asset : bool
        If True (default), at most one control can be purchased per asset.
        This is the SAFE default: because each row's Risk_Reduction_usd is
        computed independently (not jointly), summing reductions from two
        controls stacked on the same asset overstates the true combined
        effect (the risk engine's control resistance model is additive and
        capped at 1.0, not linearly additive without bound). Only set this
        to False if `scenarios` contains true joint/combined-control
        scenarios whose Risk_Reduction_usd already reflects controls being
        applied together.

    Returns
    -------
    dict with:
        selected                  -> DataFrame of chosen actions
        total_cost_usd
        total_risk_reduction_usd
        budget_utilization_pct
        n_actions_selected
        residual_eal_usd          -> org-wide EAL after applying selected
                                      actions: EAL_after for assets with a
                                      selected action, EAL_before (baseline)
                                      for assets with none
        greedy_comparison         -> same metrics for a naive "sort by
                                      ROSI" baseline, using the same
                                      one_control_per_asset constraint
    """
    if budget_usd < 0:
        raise ValueError("budget_usd must be non-negative")

    required_cols = {
        "asset_id", "control_id", "cost_usd",
        "EAL_before", "EAL_after", "Risk_Reduction_usd", "ROSI",
    }
    missing = required_cols - set(scenarios.columns)
    if missing:
        raise ValueError(f"scenarios is missing required columns: {missing}")

    df = scenarios.copy().reset_index(drop=True)
    n = len(df)

    if n == 0:
        empty = df.copy()
        return {
            "selected": empty,
            "total_cost_usd": 0.0,
            "total_risk_reduction_usd": 0.0,
            "budget_utilization_pct": 0.0,
            "n_actions_selected": 0,
            "residual_eal_usd": 0.0,
            "greedy_comparison": {
                "total_cost_usd": 0.0,
                "total_risk_reduction_usd": 0.0,
                "n_actions_selected": 0,
            },
        }

    solved = False
    # Try SciPy MILP solver first (in-process HiGHS solver, ~50ms vs ~2s external process)
    try:
        from scipy.optimize import milp, LinearConstraint, Bounds
        from scipy.sparse import lil_matrix
        import numpy as np

        c = -df["Risk_Reduction_usd"].values  # SciPy minimizes
        groups = list(df.groupby("asset_id")) if one_control_per_asset else []
        n_constraints = 1 + len(groups)
        A = lil_matrix((n_constraints, n))
        b_ub = np.zeros(n_constraints)

        # Budget constraint
        A[0, :] = df["cost_usd"].values
        b_ub[0] = budget_usd

        # One control per asset constraint
        for idx, (_, grp) in enumerate(groups):
            A[idx + 1, grp.index] = 1.0
            b_ub[idx + 1] = 1.0

        constraint = LinearConstraint(A.tocsr(), -np.inf, b_ub)
        integrality = np.ones(n)  # all binary/integer
        bounds = Bounds(0, 1)

        res = milp(c=c, integrality=integrality, bounds=bounds, constraints=constraint)
        if res.success:
            df["selected"] = [bool(round(val)) for val in res.x]
            solved = True
    except Exception:
        solved = False

    if not solved:
        # Fallback to PuLP solver
        try:
            prob = pulp.LpProblem("investment_optimization", pulp.LpMaximize)
            if hasattr(prob, "add_variable"):
                x = [prob.add_variable(name=f"x_{i}", cat="Binary") for i in range(n)]
            else:
                x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

            prob += pulp.lpSum(df.loc[i, "Risk_Reduction_usd"] * x[i] for i in range(n))
            prob += pulp.lpSum(df.loc[i, "cost_usd"] * x[i] for i in range(n)) <= budget_usd
            if one_control_per_asset:
                for asset_id, group in df.groupby("asset_id"):
                    prob += pulp.lpSum(x[i] for i in group.index) <= 1

            prob.solve(pulp.PULP_CBC_CMD(msg=False))
            if pulp.LpStatus[prob.status] == "Optimal":
                df["selected"] = [bool(round(x[i].value() or 0)) for i in range(n)]
                solved = True
        except Exception as e:
            raise RuntimeError(f"Optimizer failed: {e}")

    if not solved:
        raise RuntimeError("Optimizer did not find an optimal solution. Check budget and scenario inputs.")
    selected = df[df["selected"]].drop(columns=["selected"])

    total_cost = float(selected["cost_usd"].sum())
    total_reduction = float(selected["Risk_Reduction_usd"].sum())

    result = {
        "selected": selected,
        "total_cost_usd": total_cost,
        "total_risk_reduction_usd": total_reduction,
        "budget_utilization_pct": round(100 * total_cost / budget_usd, 2) if budget_usd else 0.0,
        "n_actions_selected": len(selected),
        "residual_eal_usd": _residual_eal(df, selected),
        "greedy_comparison": _greedy_baseline(df, budget_usd, one_control_per_asset),
    }
    return result


def _residual_eal(df: pd.DataFrame, selected: pd.DataFrame) -> float:
    """
    Org-wide EAL after applying the selected actions.

    For each asset:
      - if a selected action exists for it, use that action's EAL_after
      - otherwise, use the asset's baseline EAL_before

    Baseline EAL_before is expected to be identical across all candidate
    rows for a given asset (all computed against the same starting state),
    so we take the first occurrence per asset.
    """
    baseline_per_asset = (
        df.drop_duplicates("asset_id").set_index("asset_id")["EAL_before"]
    )

    if selected.empty:
        return float(baseline_per_asset.sum())

    selected_eal_after = selected.set_index("asset_id")["EAL_after"]
    # If one_control_per_asset was False, an asset could have more than one
    # selected row — take the minimum EAL_after (best-case / most protected)
    # as a conservative choice, and note this is only meaningful if the
    # underlying rows were independently computed.
    selected_eal_after = selected_eal_after.groupby(level=0).min()

    residual = baseline_per_asset.copy()
    residual.loc[selected_eal_after.index] = selected_eal_after
    return float(residual.sum())


def _greedy_baseline(
    df: pd.DataFrame,
    budget_usd: float,
    one_control_per_asset: bool = True,
) -> dict:
    """
    Naive baseline: sort candidate actions by ROSI (descending) and greedily
    buy them while budget allows. Respects the same one_control_per_asset
    constraint as the ILP solve, so the comparison is apples-to-apples.
    """
    ranked = df.sort_values("ROSI", ascending=False)
    spent, gained, chosen_idx = 0.0, 0.0, []
    funded_assets: set = set()

    for i, row in ranked.iterrows():
        if one_control_per_asset and row["asset_id"] in funded_assets:
            continue
        if spent + row["cost_usd"] <= budget_usd:
            spent += row["cost_usd"]
            gained += row["Risk_Reduction_usd"]
            chosen_idx.append(i)
            funded_assets.add(row["asset_id"])

    return {
        "total_cost_usd": spent,
        "total_risk_reduction_usd": gained,
        "n_actions_selected": len(chosen_idx),
    }


def run_from_parquet(
    scenario_path: str = "outputs/control_scenario_results.parquet",
    budget_usd: float = 5_000_000,
    one_control_per_asset: bool = True,
) -> dict:
    """Convenience wrapper matching the rest of the pipeline's outputs/ convention."""
    scenarios = pd.read_parquet(scenario_path)
    return optimize_investments(scenarios, budget_usd, one_control_per_asset)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 4: budget-constrained investment optimizer")
    parser.add_argument("--budget", type=float, required=True, help="Budget in USD")
    parser.add_argument(
        "--scenarios",
        default="outputs/control_scenario_results.parquet",
        help="Path to control_scenario_results.parquet",
    )
    parser.add_argument(
        "--allow-multiple-controls-per-asset",
        action="store_true",
        help=(
            "Allow more than one control to be purchased for the same asset. "
            "Off by default because independently-computed Risk_Reduction_usd "
            "values should not be summed across multiple controls on one asset."
        ),
    )
    args = parser.parse_args()

    result = run_from_parquet(
        args.scenarios,
        args.budget,
        one_control_per_asset=not args.allow_multiple_controls_per_asset,
    )

    print(f"\nBudget: ${args.budget:,.0f}")
    print(f"Selected {result['n_actions_selected']} actions")
    print(f"Total cost: ${result['total_cost_usd']:,.0f} ({result['budget_utilization_pct']}% of budget)")
    print(f"Total risk reduction: ${result['total_risk_reduction_usd']:,.0f}")
    print(f"Residual org-wide EAL after investment: ${result['residual_eal_usd']:,.0f}")

    print(f"\nGreedy (sort-by-ROSI) baseline for comparison:")
    print(f"  Total risk reduction: ${result['greedy_comparison']['total_risk_reduction_usd']:,.0f}")

    print(f"\nSelected actions:")
    print(result["selected"][["asset_id", "control_id", "cost_usd", "Risk_Reduction_usd", "ROSI"]])