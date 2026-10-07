import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from db.models import Asset, VulnerabilityFinding


class ScanNormalizer:
    """Normalizes raw scanner findings and reconciles them against dataset assets."""

    @staticmethod
    def compute_fingerprint(scanner_source: str, cve_id: str, target_host: str, port: Optional[int]) -> str:
        key = f"{scanner_source.lower()}:{cve_id.upper()}:{target_host.lower()}:{port or ''}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @classmethod
    def match_and_create_findings(
        cls,
        raw_findings: List[Dict[str, Any]],
        dataset_version_id: str,
        db: Session,
        parser_version: str = "1.0.0",
    ) -> List[VulnerabilityFinding]:
        """
        Reconciles findings with existing assets for the dataset version.
        Unmatched assets are flagged as 'unmatched' for analyst review.
        """
        # Fetch existing assets in this version
        assets = db.query(Asset).filter(Asset.dataset_version_id == dataset_version_id).all()
        
        # Build lookup maps
        by_key = {a.asset_key.lower(): a for a in assets if a.asset_key}
        by_hostname = {a.hostname.lower(): a for a in assets if a.hostname}
        
        # IP lookup: only match if unambiguous (single asset with that IP)
        ip_counts: Dict[str, List[Asset]] = {}
        for a in assets:
            if a.ip_address:
                ip_counts.setdefault(a.ip_address.strip(), []).append(a)

        now = datetime.now(timezone.utc)
        created_records: List[VulnerabilityFinding] = []

        for f in raw_findings:
            target = str(f.get("target_host", "")).strip().lower()
            port = f.get("port")
            scanner_source = f.get("scanner_source", "generic")
            cve_id = f.get("cve_id", "UNKNOWN").upper().strip()

            matched_asset: Optional[Asset] = None
            match_status = "unmatched"

            # 1. Match by asset_key
            if target in by_key:
                matched_asset = by_key[target]
                match_status = "matched"
            # 2. Match by hostname
            elif target in by_hostname:
                matched_asset = by_hostname[target]
                match_status = "matched"
            # 3. Match by IP address ONLY if exactly one asset has that IP
            elif target in ip_counts and len(ip_counts[target]) == 1:
                matched_asset = ip_counts[target][0]
                match_status = "matched"
            elif target in ip_counts and len(ip_counts[target]) > 1:
                # Ambiguous IP: require manual analyst review rather than merging
                match_status = "pending_review"

            fingerprint = cls.compute_fingerprint(scanner_source, cve_id, target, port)

            finding = VulnerabilityFinding(
                dataset_version_id=dataset_version_id,
                asset_id=matched_asset.id if matched_asset else None,
                scanner_source=scanner_source,
                source_finding_id=f.get("source_finding_id"),
                cve_id=cve_id,
                product_name=f.get("product_name"),
                package_name=f.get("package_name"),
                port=port,
                protocol=f.get("protocol", "tcp"),
                cvss_version=f.get("cvss_version", "3.1"),
                cvss_vector=f.get("cvss_vector"),
                cvss_score=float(f.get("cvss_score", 0.0)),
                severity=f.get("severity", "Medium"),
                first_seen=now,
                last_seen=now,
                match_status=match_status,
                status="open",
                evidence_ref=f.get("evidence_ref"),
                parser_version=parser_version,
                dedupe_fingerprint=fingerprint,
                created_at=now,
            )
            created_records.append(finding)

        return created_records
