import pytest
import pandas as pd
from api.v1.live_feed import _demo_events
from risk_engine.cve_catalog import load_cve_catalog, get_cves_for_os, get_cve_lookup
from risk_engine.dependency_graph import DependencyGraphEngine


def test_live_feed_event_generation():
    events = _demo_events()
    assert len(events) > 0
    for event in events:
        assert "event_id" in event
        assert "asset_id" in event
        assert "severity" in event

    # Demo events must be explicitly labeled as synthetic.
    assert all(e["source_type"] == "synthetic_demo" for e in events)


def test_cve_metadata_and_os_coherence():
    catalog = load_cve_catalog()
    assert len(catalog) >= 15

    lookup = get_cve_lookup()
    # Ensure Log4Shell is CVSS 10.0 and cross-platform
    assert "CVE-2021-44228" in lookup
    assert lookup["CVE-2021-44228"]["cvss_score"] == 10.0

    # Ensure Zerologon is Windows only
    assert "CVE-2020-1472" in lookup
    assert lookup["CVE-2020-1472"]["cvss_score"] == 10.0
    assert "Windows Server 2019" in lookup["CVE-2020-1472"]["applicable_os"]

    # Test OS filtering
    linux_cves = get_cves_for_os("Ubuntu 22.04")
    linux_ids = [c["cve_id"] for c in linux_cves]
    assert "CVE-2021-4034" in linux_ids  # PwnKit
    assert "CVE-2020-1472" not in linux_ids  # Zerologon shouldn't be in Ubuntu


def test_dependency_graph_and_propagation():
    assets_df = pd.DataFrame(
        [
            {"asset_id": "AST-1000", "hostname": "dc01", "business_unit": "IT", "criticality": 5, "os": "Windows Server 2019", "financial_value_usd": 250000},
            {"asset_id": "AST-1001", "hostname": "db01", "business_unit": "Finance", "criticality": 5, "os": "Linux", "financial_value_usd": 300000},
            {"asset_id": "AST-1002", "hostname": "app01", "business_unit": "Engineering", "criticality": 4, "os": "Linux", "financial_value_usd": 150000},
            {"asset_id": "AST-1003", "hostname": "ws01", "business_unit": "Sales", "criticality": 2, "os": "Windows 10", "financial_value_usd": 40000},
        ]
    )
    engine = DependencyGraphEngine()
    graph = engine.build_graph(assets_df=assets_df, seed=42)
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0
    # Edges are inferred, not observed topology.
    assert all(e["edge_type"] == "inferred" for e in graph["edges"])

    first_node_id = graph["nodes"][0]["asset_id"]
    prop = engine.propagate_risk(first_node_id)
    assert prop["breached_asset_id"] == first_node_id
    assert prop["cascading_eal_usd"] >= prop["initial_eal_usd"]
    assert prop["systemic_amplification_factor"] >= 1.0
    assert "nodes" in prop
    assert "edges" in prop


def test_dependency_graph_is_deterministic_and_rejects_unknown_asset():
    assets_df = pd.DataFrame(
        [
            {"asset_id": f"AST-{i}", "hostname": f"host{i}", "business_unit": "IT", "criticality": 3, "os": "Linux", "financial_value_usd": 10000}
            for i in range(10)
        ]
    )
    graph_a = DependencyGraphEngine().build_graph(assets_df=assets_df, seed=7)
    graph_b = DependencyGraphEngine().build_graph(assets_df=assets_df, seed=7)
    assert graph_a["edges"] == graph_b["edges"]

    empty = DependencyGraphEngine().build_graph(assets_df=None)
    assert empty["nodes"] == []

    engine = DependencyGraphEngine()
    engine.build_graph(assets_df=assets_df, seed=7)
    with pytest.raises(KeyError):
        engine.propagate_risk("DOES-NOT-EXIST")
