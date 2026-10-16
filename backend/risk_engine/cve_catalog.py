"""
Authoritative CVE Catalog and Metadata Registry.
Provides deterministic CVSS scores, EPSS probabilities, severity ratings,
and strict OS compatibility constraints for vulnerability generation.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CVE_METADATA_FILE = DATA_DIR / "cve_metadata.json"


def load_cve_catalog() -> List[dict]:
    """Loads the curated CVE catalog."""
    if not CVE_METADATA_FILE.exists():
        return []
    with open(CVE_METADATA_FILE, "r") as f:
        data = json.load(f)
    return data.get("cves", [])


def get_cve_lookup() -> Dict[str, dict]:
    """Returns a dictionary mapping cve_id -> CVE metadata dictionary."""
    catalog = load_cve_catalog()
    return {c["cve_id"]: c for c in catalog}


def get_cves_for_os(os_name: str) -> List[dict]:
    """Filters CVEs compatible with the given operating system."""
    catalog = load_cve_catalog()
    matching = []
    for cve in catalog:
        applicable = cve.get("applicable_os", [])
        if "Cross-platform" in applicable or os_name in applicable:
            matching.append(cve)
    return matching if matching else catalog
