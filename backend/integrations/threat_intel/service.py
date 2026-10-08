import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from db.models import ThreatIntelSnapshot
from integrations.threat_intel.epss_client import EPSSClient
from integrations.threat_intel.kev_client import CISAKEVClient


class ThreatIntelService:
    def __init__(self, db: Session):
        self.db = db
        self.epss_client = EPSSClient()
        self.kev_client = CISAKEVClient()

    def get_feed_status(self) -> Dict[str, Any]:
        """Returns the current status, freshness, and snapshot counts of threat intel feeds."""
        total_snapshots = self.db.query(ThreatIntelSnapshot).count()
        latest_snapshot = self.db.query(ThreatIntelSnapshot).order_by(ThreatIntelSnapshot.fetched_at.desc()).first()

        now = datetime.now(timezone.utc)
        ttl = settings.THREAT_INTEL_CACHE_TTL_HOURS
        is_stale = True
        if latest_snapshot and latest_snapshot.fetched_at:
            age_hours = (now - latest_snapshot.fetched_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600.0
            is_stale = age_hours > ttl

        kev_status = self.kev_client.get_catalog_status()

        if settings.THREAT_INTEL_OFFLINE_MODE:
            feed_state = "offline_sample"
        elif not latest_snapshot:
            feed_state = "no_snapshots"
        elif is_stale:
            feed_state = "stale"
        else:
            feed_state = "fresh"

        return {
            "status": feed_state,
            "is_stale": is_stale,
            "total_cached_cves": total_snapshots,
            "cisa_kev_entries_count": kev_status.get("entries"),
            "last_fetched_at": latest_snapshot.fetched_at.isoformat() if latest_snapshot else None,
            "refresh_ttl_hours": ttl,
            "sources": {
                "first_epss": {
                    "status": "offline_sample" if settings.THREAT_INTEL_OFFLINE_MODE else "operational",
                    "url": settings.EPSS_API_URL,
                },
                "cisa_kev": {
                    "status": kev_status.get("source", "not_loaded"),
                    "url": settings.CISA_KEV_URL,
                    "entries": kev_status.get("entries"),
                    "last_fetched_at": kev_status.get("last_fetched_at"),
                    "is_sample_fallback": kev_status.get("is_sample_fallback", False),
                },
            },
            "note": "EPSS/KEV values not returned by the upstream feeds are reported as unavailable, never imputed.",
        }

    def enrich_cves(self, cve_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Enriches a list of CVE IDs with EPSS and KEV data, persisting snapshots to DB.
        Returns a dictionary keyed by CVE ID.
        """
        clean_cves = list({c.strip().upper() for c in cve_list if c and c.strip().upper().startswith("CVE-")})
        if not clean_cves:
            return {}

        # 1. Fetch EPSS scores
        epss_results = self.epss_client.get_scores_batch(clean_cves)

        # 2. Check KEV catalog
        now = datetime.now(timezone.utc)
        enriched: Dict[str, Dict[str, Any]] = {}

        for cve in clean_cves:
            epss_data = epss_results.get(cve, {
                "epss": None,
                "percentile": None,
                "status": "unavailable",
                "source": "unavailable",
            })
            is_kev = self.kev_client.is_known_exploited(cve)
            kev_details = self.kev_client.get_kev_details(cve) if is_kev else None

            due_date = None
            if kev_details and kev_details.get("dueDate"):
                try:
                    due_date = datetime.strptime(kev_details["dueDate"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            date_added = None
            if kev_details and kev_details.get("dateAdded"):
                try:
                    date_added = datetime.strptime(kev_details["dateAdded"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            # Check if snapshot already exists in DB
            snapshot = self.db.scalars(
                select(ThreatIntelSnapshot).where(
                    ThreatIntelSnapshot.cve_id == cve,
                    ThreatIntelSnapshot.source == "combined",
                )
            ).first()

            resp_hash = hashlib.sha256(f"{cve}:{epss_data.get('epss')}:{is_kev}".encode("utf-8")).hexdigest()

            if not snapshot:
                snapshot = ThreatIntelSnapshot(
                    cve_id=cve,
                    source="combined",
                    score=epss_data.get("epss"),
                    percentile=epss_data.get("percentile"),
                    is_known_exploited=is_kev,
                    kev_date_added=date_added,
                    kev_due_date=due_date,
                    kev_required_action=kev_details.get("requiredAction") if kev_details else None,
                    response_hash=resp_hash,
                    status=epss_data.get("status", "fresh"),
                    fetched_at=now,
                )
                self.db.add(snapshot)
            else:
                snapshot.score = epss_data.get("epss")
                snapshot.percentile = epss_data.get("percentile")
                snapshot.is_known_exploited = is_kev
                snapshot.response_hash = resp_hash
                snapshot.status = epss_data.get("status", "fresh")
                snapshot.fetched_at = now

            enriched[cve] = {
                "cve_id": cve,
                "epss_score": epss_data.get("epss"),
                "epss_percentile": epss_data.get("percentile"),
                "is_known_exploited": is_kev,
                "kev_due_date": due_date.isoformat() if due_date else None,
                "kev_required_action": kev_details.get("requiredAction") if kev_details else None,
                "status": epss_data.get("status", "unavailable"),
                "source": epss_data.get("source"),
                "snapshot_id": snapshot.id,
            }

        self.db.commit()
        return enriched
