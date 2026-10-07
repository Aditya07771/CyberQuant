import csv
import io
import re
from typing import Any, Dict, List


class AppSecCSVParser:
    """Parser for AppSec / SCA / SAST CSV scan exports."""

    @staticmethod
    def parse(csv_content: str) -> List[Dict[str, Any]]:
        if not csv_content or not csv_content.strip():
            raise ValueError("Empty AppSec CSV content")

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            raise ValueError(f"Invalid CSV structure: {str(e)}")

        findings: List[Dict[str, Any]] = []

        for row in reader:
            normalized_row = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}

            # Identify target asset/host/repo
            target_host = (
                normalized_row.get("asset_id")
                or normalized_row.get("hostname")
                or normalized_row.get("repository")
                or normalized_row.get("project")
                or normalized_row.get("application")
                or normalized_row.get("target")
                or "appsec-target"
            )

            # Identify CVE / vulnerability ID
            cve_id = (
                normalized_row.get("cve_id")
                or normalized_row.get("cve")
                or normalized_row.get("vulnerability_id")
                or normalized_row.get("issue_id")
                or ""
            )

            if not cve_id.upper().startswith("CVE-"):
                # Try finding in title/description
                desc = normalized_row.get("description") or normalized_row.get("title") or ""
                matches = re.findall(r"CVE-\d{4}-\d{4,7}", desc, re.IGNORECASE)
                if matches:
                    cve_id = matches[0].upper()
                else:
                    cve_id = cve_id.upper() if cve_id else f"APPSEC-{len(findings) + 1}"

            score_str = (
                normalized_row.get("cvss_score")
                or normalized_row.get("cvss")
                or normalized_row.get("score")
                or "0.0"
            )
            try:
                cvss_score = float(score_str)
            except ValueError:
                cvss_score = 0.0

            severity = (
                normalized_row.get("severity")
                or normalized_row.get("priority")
                or ("Critical" if cvss_score >= 9.0 else "High" if cvss_score >= 7.0 else "Medium")
            )

            package = normalized_row.get("package") or normalized_row.get("component") or normalized_row.get("library")
            file_path = normalized_row.get("file_path") or normalized_row.get("file") or normalized_row.get("location")
            solution = normalized_row.get("remediation") or normalized_row.get("fix") or normalized_row.get("solution") or ""

            evidence = f"Package: {package or 'N/A'}. File: {file_path or 'N/A'}. Fix: {solution}"

            findings.append({
                "scanner_source": "appsec_csv",
                "source_finding_id": normalized_row.get("id") or normalized_row.get("issue_key") or f"ROW-{len(findings) + 1}",
                "target_host": target_host,
                "port": None,
                "protocol": "tcp",
                "cve_id": cve_id,
                "product_name": package or "AppSec Component",
                "cvss_version": "3.1",
                "cvss_vector": normalized_row.get("cvss_vector"),
                "cvss_score": cvss_score,
                "severity": severity.capitalize(),
                "evidence_ref": evidence,
            })

        return findings
