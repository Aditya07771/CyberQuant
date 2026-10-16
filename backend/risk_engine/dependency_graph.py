"""
Active Directory Asset Dependency & Systemic Risk Propagation Engine.

Models lateral movement attack pathways across operational and enterprise assets,
and calculates cascading financial risk exposure from any initial breach entrypoint.
"""

import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


class DependencyGraphEngine:
    """
    Constructs an Active Directory-style dependency graph and computes
    probabilistic multi-hop risk propagation.
    """

    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.edges: List[dict] = []
        self._built = False

    def build_graph(self, assets_df: Optional[pd.DataFrame] = None) -> dict:
        """Construct the AD topology from the current asset inventory."""
        if assets_df is None or assets_df.empty:
            assets_path = DATA_DIR / "assets.csv"
            if assets_path.exists():
                assets_df = pd.read_csv(assets_path)
            else:
                assets_df = pd.DataFrame()

        if assets_df.empty:
            return {"nodes": [], "edges": []}

        # Load risk summary if available for actual financial values
        risk_map = {}
        risk_parquet = OUTPUT_DIR / "asset_risk_summary.parquet"
        if risk_parquet.exists():
            try:
                rdf = pd.read_parquet(risk_parquet)
                for _, r in rdf.iterrows():
                    risk_map[str(r.get("asset_id"))] = {
                        "EAL_usd": float(r.get("EAL_usd", 10000)),
                        "VaR95_usd": float(r.get("VaR95_usd", 35000)),
                        "priority_score": float(r.get("priority_score", 5000)),
                    }
            except Exception:
                pass

        self.nodes = {}
        self.edges = []

        # Categorize assets into realistic Active Directory tiers
        assets_list = assets_df.to_dict(orient="records")
        for i, a in enumerate(assets_list):
            aid = str(a.get("asset_id", f"AST-{1000+i}"))
            hostname = str(a.get("hostname", f"host-{aid}.internal"))
            bu = str(a.get("business_unit", "Operations"))
            crit = int(a.get("criticality", 3))
            os_name = str(a.get("os", "Linux"))
            fin_val = float(a.get("financial_value_usd", 50000))

            # Role heuristic
            if i == 0 or "dc" in hostname.lower() or (crit == 5 and "Server" in os_name):
                role = "Domain Controller"
                tier = 0
            elif "sql" in hostname.lower() or "db" in hostname.lower() or (crit >= 4 and bu in ["Finance", "Engineering"]):
                role = "Core Database"
                tier = 1
            elif "app" in hostname.lower() or "web" in hostname.lower() or crit >= 3:
                role = "Application Server"
                tier = 2
            elif "admin" in hostname.lower() or (crit >= 3 and "Windows 10" in os_name):
                role = "Admin Workstation"
                tier = 3
            else:
                role = "User Endpoint"
                tier = 4

            r_data = risk_map.get(aid, {"EAL_usd": fin_val * 0.12, "VaR95_usd": fin_val * 0.35, "priority_score": fin_val * 0.08})

            self.nodes[aid] = {
                "asset_id": aid,
                "hostname": hostname,
                "business_unit": bu,
                "criticality": crit,
                "os": os_name,
                "financial_value_usd": fin_val,
                "role": role,
                "tier": tier,
                "EAL_usd": round(r_data["EAL_usd"], 2),
                "VaR95_usd": round(r_data["VaR95_usd"], 2),
            }

        # Build realistic directed trust & lateral movement edges
        node_ids = list(self.nodes.keys())
        dcs = [nid for nid, n in self.nodes.items() if n["tier"] == 0]
        dbs = [nid for nid, n in self.nodes.items() if n["tier"] == 1]
        apps = [nid for nid, n in self.nodes.items() if n["tier"] == 2]
        admins = [nid for nid, n in self.nodes.items() if n["tier"] == 3]
        users = [nid for nid, n in self.nodes.items() if n["tier"] == 4]

        # Ensure at least 1 DC and 1 DB
        if not dcs and node_ids:
            dcs = [node_ids[0]]
            self.nodes[dcs[0]]["role"] = "Domain Controller"
            self.nodes[dcs[0]]["tier"] = 0
        if not dbs and len(node_ids) > 1:
            dbs = [node_ids[1]]
            self.nodes[dbs[0]]["role"] = "Core Database"
            self.nodes[dbs[0]]["tier"] = 1

        added_edge_keys: Set[Tuple[str, str]] = set()

        def add_edge(src: str, dst: str, proto: str, prob: float, desc: str):
            if src == dst:
                return
            key = (src, dst)
            if key not in added_edge_keys:
                added_edge_keys.add(key)
                self.edges.append({
                    "source": src,
                    "target": dst,
                    "protocol": proto,
                    "lateral_movement_probability": round(prob, 2),
                    "attack_vector": desc,
                })

        # 1. User Endpoints -> App Servers (Standard network traffic, HTTP/SMB)
        for u in users:
            target_apps = random.sample(apps, min(len(apps), random.randint(1, 2))) if apps else []
            for app in target_apps:
                add_edge(u, app, "HTTP/SMB", random.uniform(0.65, 0.85), "Web Application / API Exploitation")

        # 2. User Endpoints -> Admin Workstations (Phishing / Kerberoasting pivot)
        for u in users[: len(users) // 2]:
            if admins:
                target_admin = random.choice(admins)
                add_edge(u, target_admin, "Kerberos/RPC", random.uniform(0.40, 0.60), "Credential Harvesting / Kerberoasting")

        # 3. App Servers -> Core Databases (DB connections, SQL injection / trusted links)
        for app in apps:
            target_dbs = random.sample(dbs, min(len(dbs), random.randint(1, 2))) if dbs else []
            for db in target_dbs:
                add_edge(app, db, "TDS/PostgreSQL", random.uniform(0.70, 0.90), "Service Account Impersonation / Direct DB Access")

        # 4. Admin Workstations -> Domain Controllers (DCSync / Pass-the-Hash)
        for admin in admins:
            for dc in dcs:
                add_edge(admin, dc, "LDAP/RPC", random.uniform(0.75, 0.95), "DCSync & Remote Registry Admin Compromise")

        # 5. Domain Controllers -> All other assets (Golden Ticket / GPO push)
        for dc in dcs:
            for dst in random.sample(node_ids, min(len(node_ids), 12)):
                if dst != dc:
                    add_edge(dc, dst, "GPO/WMI", random.uniform(0.92, 0.99), "Domain Admin Takeover / GPO Malicious Push")

        # 6. Same-BU lateral movement (peer-to-peer SMB / SSH)
        for nid in node_ids:
            bu = self.nodes[nid]["business_unit"]
            peers = [p for p in node_ids if p != nid and self.nodes[p]["business_unit"] == bu]
            if peers:
                target_peer = random.choice(peers)
                add_edge(nid, target_peer, "SMB/SSH", random.uniform(0.35, 0.55), "Subnet Lateral Pivot")

        self._built = True
        return {
            "nodes": list(self.nodes.values()),
            "edges": self.edges,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
        }

    def propagate_risk(self, breached_asset_id: str) -> dict:
        """
        Calculates lateral movement compromise probability and cascading financial
        loss exposure if breached_asset_id is compromised.
        """
        if not self._built or not self.nodes:
            self.build_graph()

        if breached_asset_id not in self.nodes:
            # Fallback to first node
            breached_asset_id = list(self.nodes.keys())[0] if self.nodes else "AST-1000"

        # Build adjacency list: node -> list of (target, prob, edge_dict)
        adj: Dict[str, List[Tuple[str, float, dict]]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            adj[e["source"]].append((e["target"], float(e["lateral_movement_probability"]), e))

        # Max-probability path search (Dijkstra-variant using -log(prob) or direct product)
        # Prob(node) = max probability across all paths
        comp_prob: Dict[str, float] = {nid: 0.0 for nid in self.nodes}
        hops: Dict[str, int] = {nid: -1 for nid in self.nodes}
        parent_edge: Dict[str, Optional[dict]] = {nid: None for nid in self.nodes}

        comp_prob[breached_asset_id] = 1.0
        hops[breached_asset_id] = 0

        # Queue / relaxation
        queue = [(breached_asset_id, 1.0, 0)]
        visited_iterations = 0
        max_iterations = 500

        while queue and visited_iterations < max_iterations:
            visited_iterations += 1
            # Pop node with highest current prob
            queue.sort(key=lambda x: x[1], reverse=True)
            curr_id, curr_p, curr_hop = queue.pop(0)

            if curr_p < comp_prob[curr_id] and curr_id != breached_asset_id:
                continue

            for nxt_id, edge_p, edge_dict in adj.get(curr_id, []):
                new_p = curr_p * edge_p
                # Only propagate if meaningful (> 0.05) and improves probability
                if new_p > comp_prob[nxt_id] and new_p >= 0.05:
                    comp_prob[nxt_id] = new_p
                    hops[nxt_id] = curr_hop + 1
                    parent_edge[nxt_id] = edge_dict
                    queue.append((nxt_id, new_p, curr_hop + 1))

        # Calculate systemic financial impact metrics
        initial_node = self.nodes.get(breached_asset_id, {})
        initial_eal = initial_node.get("EAL_usd", 10000.0)

        cascading_eal = 0.0
        cascading_var95 = 0.0
        downstream_compromised_count = 0

        node_impact_list = []
        for nid, node in self.nodes.items():
            p = round(comp_prob[nid], 3)
            h = hops[nid]
            node_eal = node["EAL_usd"]
            expected_loss = round(node_eal * p, 2)

            cascading_eal += expected_loss
            cascading_var95 += node["VaR95_usd"] * p

            if p >= 0.4 and nid != breached_asset_id:
                downstream_compromised_count += 1

            node_impact_list.append({
                **node,
                "compromise_probability": p,
                "hops_from_breach": h,
                "expected_cascading_eal_usd": expected_loss,
                "is_initial_breach": (nid == breached_asset_id),
            })

        # Sort nodes by compromise probability and EAL
        node_impact_list.sort(key=lambda x: (x["compromise_probability"], x["expected_cascading_eal_usd"]), reverse=True)

        # Identify critical lateral movement paths (edges on compromised routes)
        active_edges = []
        for e in self.edges:
            src_p = comp_prob.get(e["source"], 0.0)
            dst_p = comp_prob.get(e["target"], 0.0)
            is_active = (src_p >= 0.2 and dst_p >= 0.15)
            active_edges.append({
                **e,
                "is_active_path": is_active,
                "path_risk_score": round(src_p * float(e["lateral_movement_probability"]), 3),
            })

        systemic_amplification = round(cascading_eal / max(initial_eal, 1.0), 2)

        return {
            "breached_asset_id": breached_asset_id,
            "initial_breached_asset": initial_node,
            "initial_eal_usd": initial_eal,
            "cascading_eal_usd": round(cascading_eal, 2),
            "cascading_var95_usd": round(cascading_var95, 2),
            "systemic_amplification_factor": systemic_amplification,
            "high_risk_downstream_count": downstream_compromised_count,
            "nodes": node_impact_list,
            "edges": active_edges,
        }
