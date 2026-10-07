import json
import re
from typing import Any, Dict, List, Optional


class NessusParser:
    """Parser for Nessus JSON scan exports."""

    @staticmethod
    def parse(json_content: str) -> List[Dict[str, Any]]:
        if not json_content or not json_content.strip():
            raise ValueError("Empty Nessus JSON content")

        try:
            data = json.loads(json_content)
        except Exception as e:
            raise ValueError(f"Invalid Nessus JSON format: {str(e)}")

        findings: List[Dict[str, Any]] = []

        # Nessus JSON can be a list of host items or a dictionary with findings/vulnerabilities
        host_entries = []
        if isinstance(data, list):
            host_entries = data
        elif isinstance(data, dict):
            if "vulnerabilities" in data and isinstance(data["vulnerabilities"], list):
                host_entries = [{"hostname": data.get("host", "unknown"), "vulnerabilities": data["vulnerabilities"]}]
            elif "hosts" in data and isinstance(data["hosts"], list):
                host_entries = data["hosts"]
            else:
                host_entries = [data]

        for entry in host_entries:
            hostname = entry.get("hostname") or entry.get("host") or entry.get("ip") or entry.get("asset_ip", "unknown")
            vulns = entry.get("vulnerabilities", [])

            if not vulns and ("plugin_name" in entry or "cve" in entry):
                vulns = [entry]

            for v in vulns:
                plugin_id = str(v.get("plugin_id") or v.get("id") or "")
                plugin_name = v.get("plugin_name") or v.get("name") or "Nessus Finding"

                score = 0.0
                if "cvss3_base_score" in v and v["cvss3_base_score"] is not None:
                    score = float(v["cvss3_base_score"])
                elif "cvss_base_score" in v and v["cvss_base_score"] is not None:
                    score = float(v["cvss_base_score"])
                elif "cvss_score" in v and v["cvss_score"] is not None:
                    score = float(v["cvss_score"])

                raw_cve = v.get("cve", [])
                cves = []
                if isinstance(raw_cve, list):
                    for item in raw_cve:
                        if isinstance(item, str) and item.upper().startswith("CVE-"):
                            cves.append(item.upper())
                elif isinstance(raw_cve, str) and raw_cve.upper().startswith("CVE-"):
                    cves.append(raw_cve.upper())

                if not cves and plugin_name:
                    found = re.findall(r"CVE-\d{4}-\d{4,7}", plugin_name, re.IGNORECASE)
                    cves = [c.upper() for c in found]

                port = v.get("port")
                try:
                    port_num = int(port) if port is not None else None
                except ValueError:
                    port_num = None

                protocol = str(v.get("protocol", "tcp")).lower()
                solution = v.get("solution", "")
                evidence = f"Nessus Plugin {plugin_id}: {plugin_name}. Solution: {solution}"

                severity_num = v.get("severity")
                sev_map = {0: "Info", 1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
                if isinstance(severity_num, int) and severity_num in sev_map:
                    severity_label = sev_map[severity_num]
                elif isinstance(severity_num, str):
                    severity_label = severity_num.capitalize()
                else:
                    severity_label = "High" if score >= 7.0 else ("Critical" if score >= 9.0 else "Medium")

                target_cves = cves if cves else [f"NESSUS-{plugin_id or 'FINDING'}"]
                for cve in target_cves:
                    findings.append({
                        "scanner_source": "nessus",
                        "source_finding_id": plugin_id,
                        "target_host": str(hostname),
                        "port": port_num,
                        "protocol": protocol,
                        "cve_id": cve,
                        "product_name": plugin_name,
                        "cvss_version": "3.1" if "cvss3_base_score" in v else "2.0",
                        "cvss_vector": v.get("cvss3_vector") or v.get("cvss_vector"),
                        "cvss_score": score,
                        "severity": severity_label,
                        "evidence_ref": evidence,
                    })

        return findings
