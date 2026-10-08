import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# Process-wide cache so a status query does not re-download the full catalog on
# every request. Refreshed at most once per TTL.
_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
_CATALOG_FETCHED_AT: Optional[float] = None
_CATALOG_SOURCE: str = "unknown"
CATALOG_TTL_SECONDS = 6 * 3600


class CISAKEVClient:
    """
    Client for CISA Known Exploited Vulnerabilities (KEV) Catalog.
    Provides check for known active weaponization, required actions, and offline cache.
    """

    OFFLINE_KEV_CATALOG: Dict[str, Dict[str, Any]] = {
        "CVE-2021-44228": {
            "cveID": "CVE-2021-44228",
            "vendorProject": "Apache",
            "product": "Log4j",
            "vulnerabilityName": "Apache Log4j Remote Code Execution",
            "dateAdded": "2021-12-10",
            "requiredAction": "Apply updates per vendor instructions.",
            "dueDate": "2021-12-24",
        },
        "CVE-2017-0144": {
            "cveID": "CVE-2017-0144",
            "vendorProject": "Microsoft",
            "product": "SMBv1",
            "vulnerabilityName": "Microsoft SMBv1 Remote Code Execution (EternalBlue)",
            "dateAdded": "2022-01-28",
            "requiredAction": "Apply vendor security updates or disable SMBv1.",
            "dueDate": "2022-02-11",
        },
        "CVE-2020-1472": {
            "cveID": "CVE-2020-1472",
            "vendorProject": "Microsoft",
            "product": "Netlogon",
            "vulnerabilityName": "Microsoft Netlogon Elevation of Privilege (Zerologon)",
            "dateAdded": "2021-11-03",
            "requiredAction": "Apply Microsoft patches and enforce secure RPC.",
            "dueDate": "2021-11-17",
        },
        "CVE-2024-3094": {
            "cveID": "CVE-2024-3094",
            "vendorProject": "XZ Utils",
            "product": "XZ/liblzma",
            "vulnerabilityName": "XZ Utils Supply Chain Compromise",
            "dateAdded": "2024-04-01",
            "requiredAction": "Downgrade or update to safe version 5.6.1+.",
            "dueDate": "2024-04-15",
        },
        "CVE-2023-38606": {
            "cveID": "CVE-2023-38606",
            "vendorProject": "Apple",
            "product": "iOS/macOS",
            "vulnerabilityName": "Apple Kernel Memory Corruption",
            "dateAdded": "2023-07-26",
            "requiredAction": "Apply Apple updates.",
            "dueDate": "2023-08-16",
        },
        "CVE-2021-2109": {
            "cveID": "CVE-2021-2109",
            "vendorProject": "Oracle",
            "product": "MySQL Server",
            "vulnerabilityName": "Oracle MySQL Server Component Vulnerability",
            "dateAdded": "2022-03-25",
            "requiredAction": "Apply vendor quarterly security patch.",
            "dueDate": "2022-04-08",
        },
    }

    def __init__(self, catalog_url: Optional[str] = None, timeout: float = 5.0):
        self.catalog_url = catalog_url or settings.CISA_KEV_URL
        self.timeout = timeout

    def fetch_catalog(self, force: bool = False) -> Dict[str, Dict[str, Any]]:
        """Fetches and caches the full CISA KEV catalog (process-wide, TTL-bound)."""
        global _CATALOG_CACHE, _CATALOG_FETCHED_AT, _CATALOG_SOURCE

        now = time.time()
        if not force and _CATALOG_CACHE is not None and _CATALOG_FETCHED_AT is not None:
            if now - _CATALOG_FETCHED_AT < CATALOG_TTL_SECONDS:
                return _CATALOG_CACHE

        if settings.THREAT_INTEL_OFFLINE_MODE:
            _CATALOG_CACHE = self.OFFLINE_KEV_CATALOG.copy()
            _CATALOG_FETCHED_AT = now
            _CATALOG_SOURCE = "offline_cache"
            return _CATALOG_CACHE

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(self.catalog_url)
                if resp.status_code == 200:
                    payload = resp.json()
                    vulns = payload.get("vulnerabilities", [])
                    catalog = {}
                    for v in vulns:
                        cve = v.get("cveID", "").upper().strip()
                        if cve:
                            catalog[cve] = v
                    _CATALOG_CACHE = catalog
                    _CATALOG_FETCHED_AT = now
                    _CATALOG_SOURCE = "cisa.gov"
                    return catalog
        except Exception as e:
            logger.warning("CISA KEV fetch failed: %s", str(e))

        # Keep a previously fetched live catalog rather than overwriting it with the
        # offline sample; if there is nothing cached, fall back to the sample and
        # record that it is stale.
        if _CATALOG_CACHE is None:
            _CATALOG_CACHE = self.OFFLINE_KEV_CATALOG.copy()
            _CATALOG_FETCHED_AT = now
            _CATALOG_SOURCE = "offline_cache"
        return _CATALOG_CACHE

    def get_catalog_status(self) -> Dict[str, Any]:
        """Reports catalog source/freshness without performing a network fetch."""
        if _CATALOG_CACHE is None:
            return {
                "entries": None,
                "source": "not_loaded",
                "last_fetched_at": None,
                "is_sample_fallback": False,
            }
        return {
            "entries": len(_CATALOG_CACHE),
            "source": _CATALOG_SOURCE,
            "last_fetched_at": datetime.fromtimestamp(_CATALOG_FETCHED_AT, tz=timezone.utc).isoformat()
            if _CATALOG_FETCHED_AT
            else None,
            "is_sample_fallback": _CATALOG_SOURCE == "offline_cache",
        }

    def is_known_exploited(self, cve_id: str) -> bool:
        """Returns True if the CVE is in the CISA KEV catalog."""
        clean_cve = cve_id.strip().upper()
        catalog = self.fetch_catalog()
        return clean_cve in catalog

    def get_kev_details(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Returns KEV record details for the CVE if present."""
        clean_cve = cve_id.strip().upper()
        catalog = self.fetch_catalog()
        return catalog.get(clean_cve)
