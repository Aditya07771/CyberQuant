import json
import random
import uuid
import datetime
from pathlib import Path

# Goal: Create a compiled dataset that a Risk Quantification Engine can ingest.
# This simulates the processed output of raw SIEM logs (like those from splunk/attack_data)
# augmented with business context (assets, vulnerabilities, controls).

def generate_assets(num_assets=50):
    assets = []
    business_units = ["Finance", "HR", "Engineering", "Sales", "Operations"]
    for i in range(num_assets):
        criticality = random.choices([1, 2, 3, 4, 5], weights=[10, 20, 40, 20, 10])[0]
        # Financial impact if asset is compromised (in USD)
        value = criticality * random.randint(10000, 100000)
        downtime_cost = criticality * random.randint(1000, 5000)

        if criticality >= 4:
            sensitivity = random.choice(["Confidential", "Restricted"])
        elif criticality == 3:
            sensitivity = "Internal"
        else:
            sensitivity = "Public"

        assets.append({
            "asset_id": f"AST-{1000+i}",
            "hostname": f"host-{random.randint(10,99)}-{business_units[random.randint(0,4)].lower()}.internal",
            "business_unit": random.choice(business_units),
            "criticality": criticality,
            "data_sensitivity_tier": sensitivity,
            "financial_value_usd": value,
            "downtime_cost_per_hour_usd": downtime_cost,
            "regulatory_penalty_potential_usd": random.choice([0, 50000, 250000, 1000000]) if criticality >= 4 else 0,
            "os": random.choice(["Windows Server 2019", "Ubuntu 22.04", "RHEL 8", "Windows 10"])
        })
    return assets


def generate_vulnerabilities(assets, num_vulns=120):
    """
    Generates vulnerability findings respecting authoritative CVE metadata:
    - OS compatibility: Windows CVEs only on Windows, Linux on Linux.
    - Deterministic CVSS and EPSS scores: same CVE always carries identical severity.
    """
    import json
    data_dir = Path(__file__).resolve().parents[1] / "data"
    cve_file = data_dir / "cve_metadata.json"

    catalog = []
    if cve_file.exists():
        with open(cve_file, "r") as f:
            catalog = json.load(f).get("cves", [])

    if not catalog:
        catalog = [
            {"cve_id": "CVE-2021-44228", "cvss_score": 10.0, "epss_score": 0.975, "severity": "Critical", "applicable_os": ["Cross-platform"]},
            {"cve_id": "CVE-2020-1472", "cvss_score": 10.0, "epss_score": 0.945, "severity": "Critical", "applicable_os": ["Windows Server 2019"]},
            {"cve_id": "CVE-2019-0708", "cvss_score": 9.8, "epss_score": 0.920, "severity": "Critical", "applicable_os": ["Windows Server 2019", "Windows 10"]},
            {"cve_id": "CVE-2021-4034", "cvss_score": 7.8, "epss_score": 0.840, "severity": "High", "applicable_os": ["Ubuntu 22.04", "RHEL 8"]},
            {"cve_id": "CVE-2022-0847", "cvss_score": 7.8, "epss_score": 0.860, "severity": "High", "applicable_os": ["Ubuntu 22.04", "RHEL 8"]},
        ]

    # Map each OS to compatible CVEs
    def get_cves_for_asset_os(os_str):
        matches = []
        for item in catalog:
            app_os = item.get("applicable_os", [])
            if "Cross-platform" in app_os or os_str in app_os:
                matches.append(item)
        return matches if matches else catalog

    vulns = []
    # Ensure every asset has at least 1-3 vulnerabilities
    for i in range(num_vulns):
        target_asset = random.choice(assets)
        compatible_cves = get_cves_for_asset_os(target_asset.get("os", ""))
        cve_meta = random.choice(compatible_cves)

        vulns.append({
            "vuln_id": f"VULN-{uuid.uuid4().hex[:8]}",
            "asset_id": target_asset["asset_id"],
            "cve_id": cve_meta["cve_id"],
            "cvss_score": float(cve_meta["cvss_score"]),
            "epss_score": float(cve_meta["epss_score"]),
            "severity": cve_meta["severity"],
            "status": random.choice(["Open", "In Progress", "Risk Accepted"]),
            "discovery_date": (datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 100))).isoformat()
        })
    return vulns


def generate_threat_events(assets, num_events=200):
    """
    Simulates parsed events from datasets like splunk/attack_data.
    This acts as historical incident data to train the likelihood model.
    """
    events = []
    attack_types = [
        ("T1059.001", "PowerShell Execution", "Medium"),
        ("T1110.001", "Password Guessing", "Low"),
        ("T1003.001", "LSASS Memory Credential Dumping", "High"),
        ("T1486", "Data Encrypted for Impact (Ransomware)", "Critical"),
        ("T1078", "Valid Accounts", "Medium")
    ]
    for i in range(num_events):
        attack = random.choice(attack_types)
        action = random.choice(["Blocked", "Allowed", "Alerted"])

        # Simulate financial impact variables if the attack succeeded
        downtime_hours = 0
        records_compromised = 0
        if action == "Allowed":
            if attack[2] == "Critical":
                downtime_hours = random.randint(4, 72)
            elif attack[2] == "High":
                records_compromised = random.randint(100, 50000)

        events.append({
            "event_id": f"EVT-{uuid.uuid4().hex[:8]}",
            "timestamp": (datetime.datetime.now() - datetime.timedelta(hours=random.randint(1, 720))).isoformat(),
            "asset_id": random.choice(assets)["asset_id"],
            "mitre_technique_id": attack[0],
            "description": attack[1],
            "severity": attack[2],
            "source_ip": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            "action_taken": action,
            "downtime_hours_caused": downtime_hours,
            "records_compromised": records_compromised
        })
    return events


def generate_controls():
    """
    Security control catalog with GENUINE cost/effectiveness trade-offs.
    Reads from compliance_mappings.json.
    """
    import json
    from pathlib import Path
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    mappings_file = data_dir / "compliance_mappings.json"
    
    controls = []
    if mappings_file.exists():
        with open(mappings_file, "r") as f:
            data = json.load(f)
        for ctrl_id, ctrl_data in data.get("control_mappings", {}).items():
            controls.append({
                "control_id": ctrl_id,
                "name": ctrl_data["name"],
                "risk_reduction_pct": ctrl_data.get("risk_reduction_pct", 0.5),
                "cost_usd": ctrl_data.get("cost_usd", 10000)
            })
    else:
        controls = [
            {"control_id": "CTRL-01", "name": "Endpoint Detection & Response (EDR)", "risk_reduction_pct": 0.75, "cost_usd": 45000},
            {"control_id": "CTRL-02", "name": "Multi-Factor Authentication (MFA)", "risk_reduction_pct": 0.60, "cost_usd": 15000},
            {"control_id": "CTRL-03", "name": "Network Segmentation", "risk_reduction_pct": 0.90, "cost_usd": 95000},
            {"control_id": "CTRL-04", "name": "Regular Patching Program", "risk_reduction_pct": 0.55, "cost_usd": 18000},
            {"control_id": "CTRL-05", "name": "Security Information & Event Management (SIEM)", "risk_reduction_pct": 0.80, "cost_usd": 65000},
        ]
    return controls


def generate_asset_controls(assets, controls):
    """
    Creates a mapping of which controls are CURRENTLY deployed on which assets.
    """
    deployed_controls = []
    
    # Randomly select a subset of controls that this organization actually owns.
    # If they only own 12 out of 20 controls, the other 8 will guarantee organizational gaps!
    org_owned_controls = random.sample(controls, k=12)
    
    for asset in assets:
        deploy_probability = 0.15 * (asset["criticality"] / 5.0)

        selected_controls = [
            ctrl for ctrl in org_owned_controls if random.random() < deploy_probability
        ]

        for ctrl in selected_controls:
            deployed_controls.append({
                "mapping_id": f"MAP-{uuid.uuid4().hex[:8]}",
                "asset_id": asset["asset_id"],
                "control_id": ctrl["control_id"],
                "status": "Deployed",
                "deployment_date": (datetime.datetime.now() - datetime.timedelta(days=random.randint(30, 365))).isoformat()
            })
    return deployed_controls


def main():
    assets = generate_assets(50)
    vulns = generate_vulnerabilities(assets, 120)
    events = generate_threat_events(assets, 300)
    controls = generate_controls()
    asset_controls = generate_asset_controls(assets, controls)

    dataset = {
        "metadata": {
            "generated_at": datetime.datetime.now().isoformat(),
            "description": "Compiled cyber risk dataset simulating augmented Splunk Attack Data for Risk Quantification"
        },
        "assets": assets,
        "vulnerabilities": vulns,
        "threat_events": events,
        "controls": controls,
        "asset_controls": asset_controls
    }

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    output_dir = PROJECT_ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    import csv

    def write_csv(filename, data_list):
        if not data_list:
            return
        file_path = output_dir / filename
        with open(file_path, "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data_list[0].keys())
            writer.writeheader()
            writer.writerows(data_list)

    write_csv("assets.csv", assets)
    write_csv("vulnerabilities.csv", vulns)
    write_csv("threat_events.csv", events)
    write_csv("controls.csv", controls)
    write_csv("asset_controls.csv", asset_controls)

    # Also write the compiled JSON (kept for reference/inspection; the CSVs
    # remain the single source of truth consumed by risk_engine).
    with open(output_dir / "compiled_risk_dataset.json", "w") as f:
        json.dump(dataset, f, indent=2, default=str)

    print(f"Dataset successfully compiled and saved as CSV files in {output_dir}")
    print(f"Total Assets: {len(assets)}")
    print(f"Total Vulnerabilities: {len(vulns)}")
    print(f"Total Threat Events: {len(events)}")
    print(f"Total Controls: {len(controls)}")
    print(f"Total Asset-Control Mappings: {len(asset_controls)}")


if __name__ == "__main__":
    main()