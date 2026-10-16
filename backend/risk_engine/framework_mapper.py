"""
Compliance Framework Mapping Engine.

Maps deployed security controls to regulatory framework requirements
(NIST CSF 2.0, ISO 27001, CIS Controls v8, RBI CSF, SEBI CSCRF)
and computes coverage posture and compliance gaps.
"""

import json
from pathlib import Path
from typing import Dict, List, Set


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAPPINGS_FILE = DATA_DIR / "compliance_mappings.json"


def _load_mappings() -> dict:
    """Load the compliance_mappings.json file."""
    with open(MAPPINGS_FILE, "r") as f:
        return json.load(f)


def get_compliance_posture(deployed_control_ids: Set[str]) -> dict:
    """
    Compute compliance coverage posture across all frameworks.

    Parameters
    ----------
    deployed_control_ids : set of str
        Set of control IDs currently deployed (e.g. {"CTRL-01", "CTRL-02"}).

    Returns
    -------
    dict with:
        frameworks : list of dicts, each containing:
            framework_id, name, short_name, coverage_pct,
            controls_mapped, total_controls, covered_ids, gap_ids
        overall_score : float (average coverage across frameworks)
        total_controls_deployed : int
        total_controls_available : int
    """
    mappings_data = _load_mappings()
    frameworks_meta = mappings_data["frameworks"]
    control_mappings = mappings_data["control_mappings"]

    # For each framework, collect which framework control IDs are covered
    # by the deployed controls
    framework_results = []

    for fw_id, fw_meta in frameworks_meta.items():
        # Collect ALL framework control IDs that ANY control maps to
        all_fw_control_ids: Set[str] = set()
        covered_fw_control_ids: Set[str] = set()
        mapped_controls: List[str] = []

        for ctrl_id, ctrl_data in control_mappings.items():
            fw_ctrl_ids = ctrl_data.get(fw_id, [])
            all_fw_control_ids.update(fw_ctrl_ids)

            if ctrl_id in deployed_control_ids and fw_ctrl_ids:
                covered_fw_control_ids.update(fw_ctrl_ids)
                mapped_controls.append(ctrl_id)

        total = len(all_fw_control_ids) if all_fw_control_ids else 1
        covered = len(covered_fw_control_ids)
        coverage_pct = round((covered / total) * 100, 1) if total > 0 else 0.0

        gap_ids = sorted(all_fw_control_ids - covered_fw_control_ids)

        framework_results.append({
            "framework_id": fw_id,
            "name": fw_meta["name"],
            "short_name": fw_meta["short_name"],
            "coverage_pct": coverage_pct,
            "controls_covered": covered,
            "controls_total": total,
            "covered_ids": sorted(covered_fw_control_ids),
            "gap_ids": gap_ids,
            "mapped_controls": mapped_controls,
        })

    overall = (
        sum(f["coverage_pct"] for f in framework_results) / len(framework_results)
        if framework_results
        else 0.0
    )

    return {
        "frameworks": framework_results,
        "overall_score": round(overall, 1),
        "total_controls_deployed": len(deployed_control_ids),
        "total_controls_available": len(control_mappings),
    }


def get_compliance_gaps(deployed_control_ids: Set[str]) -> list:
    """
    Identify specific compliance gaps — framework requirements not
    covered by any deployed control.

    Returns a list of gap dicts, each with:
        framework_id, framework_name, gap_control_id,
        recommended_control_id, recommended_control_name,
        control_cost_usd, severity
    """
    mappings_data = _load_mappings()
    frameworks_meta = mappings_data["frameworks"]
    control_mappings = mappings_data["control_mappings"]

    gaps = []

    for fw_id, fw_meta in frameworks_meta.items():
        # Build a reverse map: framework_control_id -> list of controls that cover it
        reverse_map: Dict[str, List[dict]] = {}
        for ctrl_id, ctrl_data in control_mappings.items():
            fw_ctrl_ids = ctrl_data.get(fw_id, [])
            for fw_ctrl_id in fw_ctrl_ids:
                if fw_ctrl_id not in reverse_map:
                    reverse_map[fw_ctrl_id] = []
                reverse_map[fw_ctrl_id].append({
                    "control_id": ctrl_id,
                    "name": ctrl_data["name"],
                    "cost_usd": ctrl_data.get("cost_usd", 0),
                    "risk_reduction_pct": ctrl_data.get("risk_reduction_pct", 0),
                })

        # Find uncovered framework controls
        for fw_ctrl_id, covering_controls in reverse_map.items():
            is_covered = any(
                c["control_id"] in deployed_control_ids for c in covering_controls
            )
            if not is_covered:
                # Recommend the cheapest control that covers this gap
                best = min(covering_controls, key=lambda c: c["cost_usd"])
                severity = "High" if best["risk_reduction_pct"] >= 0.6 else (
                    "Medium" if best["risk_reduction_pct"] >= 0.4 else "Low"
                )
                gaps.append({
                    "framework_id": fw_id,
                    "framework_name": fw_meta["short_name"],
                    "gap_control_id": fw_ctrl_id,
                    "recommended_control_id": best["control_id"],
                    "recommended_control_name": best["name"],
                    "control_cost_usd": best["cost_usd"],
                    "risk_reduction_pct": best["risk_reduction_pct"],
                    "severity": severity,
                })

    # Sort by severity (High first) then framework
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    gaps.sort(key=lambda g: (severity_order.get(g["severity"], 3), g["framework_id"]))
    return gaps
