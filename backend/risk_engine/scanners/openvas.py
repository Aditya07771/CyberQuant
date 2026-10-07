import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import defusedxml.ElementTree as ET


class OpenVASParser:
    """Safe OpenVAS / Greenbone XML report parser using defusedxml."""

    @staticmethod
    def parse(xml_content: str) -> List[Dict[str, Any]]:
        if not xml_content or not xml_content.strip():
            raise ValueError("Empty OpenVAS XML content")

        try:
            root = ET.fromstring(xml_content.encode("utf-8") if isinstance(xml_content, str) else xml_content)
        except Exception as e:
            raise ValueError(f"Malformed or unsafe OpenVAS XML: {str(e)}")

        findings: List[Dict[str, Any]] = []

        # OpenVAS XML has <result> elements either directly or inside <report><report>
        for result in root.iter("result"):
            result_id = result.attrib.get("id", "")

            host_elem = result.find("host")
            host_text = host_elem.text.strip() if host_elem is not None and host_elem.text else ""

            port_elem = result.find("port")
            port_text = port_elem.text.strip() if port_elem is not None and port_elem.text else ""
            port_num = None
            protocol = "tcp"
            if "/" in port_text:
                parts = port_text.split("/")
                try:
                    port_num = int(parts[0])
                except ValueError:
                    port_num = None
                protocol = parts[1].lower()
            elif port_text.isdigit():
                port_num = int(port_text)

            severity_elem = result.find("severity")
            try:
                cvss_score = float(severity_elem.text) if severity_elem is not None and severity_elem.text else 0.0
            except ValueError:
                cvss_score = 0.0

            threat_elem = result.find("threat")
            threat = threat_elem.text.strip() if threat_elem is not None and threat_elem.text else "Medium"

            desc_elem = result.find("description")
            description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

            nvt = result.find("nvt")
            product_name = None
            cves: List[str] = []
            solution = ""
            cvss_vector = ""

            if nvt is not None:
                name_elem = nvt.find("name")
                if name_elem is not None and name_elem.text:
                    product_name = name_elem.text.strip()

                solution_elem = nvt.find("solution")
                if solution_elem is not None and solution_elem.text:
                    solution = solution_elem.text.strip()

                cve_elem = nvt.find("cve")
                if cve_elem is not None and cve_elem.text:
                    raw_cves = cve_elem.text.strip()
                    if raw_cves and raw_cves.upper() != "NOCVE":
                        for item in raw_cves.split(","):
                            clean = item.strip().upper()
                            if clean.startswith("CVE-"):
                                cves.append(clean)

                cvss_base_elem = nvt.find("cvss_base_vector")
                if cvss_base_elem is not None and cvss_base_elem.text:
                    cvss_vector = cvss_base_elem.text.strip()

            if not cves:
                # Check for CVE anywhere in description
                import re
                found_cves = re.findall(r"CVE-\d{4}-\d{4,7}", description, re.IGNORECASE)
                cves = [c.upper() for c in found_cves]

            # If still no CVE, record as generic finding if CVSS score > 0
            cve_targets = cves if cves else [f"OPENVAS-{result_id or 'FINDING'}"]

            for cve in cve_targets:
                evidence = f"OpenVAS Finding {result_id}. Solution: {solution}. Details: {description[:200]}"
                findings.append({
                    "scanner_source": "openvas",
                    "source_finding_id": result_id,
                    "target_host": host_text,
                    "port": port_num,
                    "protocol": protocol,
                    "cve_id": cve,
                    "product_name": product_name,
                    "cvss_version": "3.1" if "CVSS:3" in cvss_vector else "2.0",
                    "cvss_vector": cvss_vector or None,
                    "cvss_score": cvss_score,
                    "severity": threat,
                    "evidence_ref": evidence,
                })

        return findings
