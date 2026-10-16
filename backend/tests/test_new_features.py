import pytest
import pandas as pd
from api.live_feed import generate_live_event, get_recent_events
from risk_engine.cve_catalog import load_cve_catalog, get_cves_for_os, get_cve_lookup
from risk_engine.dependency_graph import DependencyGraphEngine


def test_live_feed_event_generation():
    event = generate_live_event()
    assert "event_id" in event
    assert "asset_id" in event
    assert "event_type" in event
    assert "impact" in event
    assert "new_eal_usd" in event["impact"]
    assert "delta_eal_usd" in event["impact"]

    recent = get_recent_events()
    assert "events" in recent
    assert len(recent["events"]) > 0


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
    engine = DependencyGraphEngine()
    graph = engine.build_graph()
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0

    first_node_id = graph["nodes"][0]["asset_id"]
    prop = engine.propagate_risk(first_node_id)
    assert prop["breached_asset_id"] == first_node_id
    assert prop["cascading_eal_usd"] >= prop["initial_eal_usd"]
    assert prop["systemic_amplification_factor"] >= 1.0
    assert "nodes" in prop
    assert "edges" in prop
