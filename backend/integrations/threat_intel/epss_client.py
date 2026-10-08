import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class EPSSClient:
    """
    Client for FIRST.org Exploit Prediction Scoring System (EPSS).
    Provides single/batch lookups, cached snapshots, bounded retries, and offline fallback.
    """

    OFFLINE_CACHE: Dict[str, Dict[str, Any]] = {
        "CVE-2021-44228": {"epss": 0.9754, "percentile": 0.9998, "date": "2024-01-01"},  # Log4Shell
        "CVE-2023-48795": {"epss": 0.0432, "percentile": 0.7250, "date": "2024-01-01"},  # Terrapin
        "CVE-2023-38606": {"epss": 0.8920, "percentile": 0.9850, "date": "2024-01-01"},
        "CVE-2017-0144":  {"epss": 0.9630, "percentile": 0.9980, "date": "2024-01-01"},  # EternalBlue
        "CVE-2020-1472":  {"epss": 0.9420, "percentile": 0.9910, "date": "2024-01-01"},  # Zerologon
        "CVE-2024-3094":  {"epss": 0.7840, "percentile": 0.9620, "date": "2024-03-30"},  # XZ Utils
        "CVE-2021-2109":  {"epss": 0.3540, "percentile": 0.8100, "date": "2024-01-01"},
        "CVE-2020-14145": {"epss": 0.0820, "percentile": 0.6500, "date": "2024-01-01"},
    }

    def __init__(self, api_url: Optional[str] = None, timeout: float = 4.0):
        self.api_url = api_url or settings.EPSS_API_URL
        self.timeout = timeout

    def get_score(self, cve_id: str) -> Dict[str, Any]:
        """
        Synchronously fetches EPSS probability and percentile rank for a single CVE.
        Returns dict with keys: epss, percentile, date, status ('fresh', 'stale', 'unavailable').
        """
        clean_cve = cve_id.strip().upper()
        if settings.THREAT_INTEL_OFFLINE_MODE:
            return self._fallback_score(clean_cve, status="stale")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                for attempt in range(2):
                    try:
                        resp = client.get(self.api_url, params={"cve": clean_cve})
                        if resp.status_code == 200:
                            data = resp.json().get("data", [])
                            if data:
                                item = data[0]
                                epss_val = item.get("epss")
                                pct_val = item.get("percentile")
                                return {
                                    "epss": float(epss_val) if epss_val is not None else None,
                                    "percentile": float(pct_val) if pct_val is not None else None,
                                    "date": item.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                    "status": "fresh",
                                    "source": "api.first.org",
                                }
                        elif resp.status_code == 429:
                            time.sleep(1.0)
                            continue
                    except (httpx.TimeoutException, httpx.NetworkError):
                        if attempt == 0:
                            time.sleep(0.5)
                            continue
        except Exception as e:
            logger.warning("EPSS API query failed for %s: %s", clean_cve, str(e))

        return self._fallback_score(clean_cve, status="stale")

    def get_scores_batch(self, cve_list: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetches EPSS scores for multiple CVEs."""
        unique_cves = list({c.strip().upper() for c in cve_list if c})
        if not unique_cves:
            return {}

        results = {}
        # FIRST.org EPSS API supports comma-separated CVE query up to ~100
        batch_size = 50
        for i in range(0, len(unique_cves), batch_size):
            chunk = unique_cves[i:i + batch_size]
            if not settings.THREAT_INTEL_OFFLINE_MODE:
                try:
                    with httpx.Client(timeout=self.timeout + 2.0) as client:
                        resp = client.get(self.api_url, params={"cve": ",".join(chunk)})
                        if resp.status_code == 200:
                            for item in resp.json().get("data", []):
                                cve = item.get("cve", "").upper()
                                epss_val = item.get("epss")
                                pct_val = item.get("percentile")
                                results[cve] = {
                                    "epss": float(epss_val) if epss_val is not None else None,
                                    "percentile": float(pct_val) if pct_val is not None else None,
                                    "date": item.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                    "status": "fresh",
                                    "source": "api.first.org",
                                }
                except Exception as e:
                    logger.warning("EPSS batch fetch failed: %s", str(e))

            for cve in chunk:
                if cve not in results:
                    results[cve] = self._fallback_score(cve, status="stale")

        return results

    def _fallback_score(self, cve: str, status: str = "stale") -> Dict[str, Any]:
        if cve in self.OFFLINE_CACHE:
            cached = self.OFFLINE_CACHE[cve]
            return {
                "epss": cached["epss"],
                "percentile": cached["percentile"],
                "date": cached.get("date", "2024-01-01"),
                "status": status,
                "source": "offline_cache",
            }
        # No score is invented for unknown CVEs. The caller must treat this as an
        # explicit unavailable input rather than substituting a fabricated prior.
        return {
            "epss": None,
            "percentile": None,
            "date": None,
            "status": "unavailable",
            "source": "unavailable",
        }
