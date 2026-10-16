import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["Live Streaming Feed"])

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# In-memory store for real-time asset risk state
_asset_risk_state: Dict[str, dict] = {}
_event_history: List[dict] = []
MAX_EVENT_HISTORY = 50


def _load_initial_asset_risk() -> Dict[str, dict]:
    """Load latest asset risk summaries into in-memory state."""
    global _asset_risk_state
    if not _asset_risk_state:
        try:
            parquet_path = OUTPUT_DIR / "asset_risk_summary.parquet"
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                for _, row in df.iterrows():
                    aid = str(row.get("asset_id"))
                    _asset_risk_state[aid] = {
                        "asset_id": aid,
                        "business_unit": str(row.get("business_unit", "Operations")),
                        "criticality": float(row.get("criticality", 3)),
                        "EAL_usd": float(row.get("EAL_usd", 15000.0)),
                        "VaR95_usd": float(row.get("VaR95_usd", 45000.0)),
                        "VaR99_usd": float(row.get("VaR99_usd", 75000.0)),
                        "priority_score": float(row.get("priority_score", 9000.0)),
                    }
        except Exception as e:
            logger.warning(f"Could not load asset risk parquet for live feed: {e}")
    return _asset_risk_state


EVENT_TEMPLATES = [
    {
        "event_type": "new_vuln_detected",
        "severities": ["Critical", "High", "Medium"],
        "descriptions": [
            "Zero-day remote code execution vulnerability identified",
            "Critical unauthenticated API flaw detected by scanner",
            "High severity privilege escalation vector discovered",
            "Outdated dependency with known CVSS 8.8 exploit found",
        ],
        "risk_multiplier_range": (1.10, 1.28),
    },
    {
        "event_type": "exploit_attempt",
        "severities": ["High", "Critical", "Medium"],
        "descriptions": [
            "Brute force credential stuffing surge detected on SSH service",
            "SQL injection payload detected against payment microservice",
            "Automated exploit kit probe blocked by WAF with payload inspection",
            "Suspicious PowerShell execution with encoded command detected",
        ],
        "risk_multiplier_range": (1.05, 1.18),
    },
    {
        "event_type": "patch_applied",
        "severities": ["Low", "Medium"],
        "descriptions": [
            "Hotfix applied to mitigate active CVE vector",
            "Kernel security patch successfully deployed via automation",
            "Vulnerability remediated: Log4j patched to safe version",
            "Emergency configuration hardening applied across host",
        ],
        "risk_multiplier_range": (0.75, 0.90),
    },
    {
        "event_type": "control_activated",
        "severities": ["Low", "Medium"],
        "descriptions": [
            "EDR behavioral blocking agent enabled on endpoint",
            "Micro-segmentation firewall rule activated for asset subnet",
            "MFA enforcement successfully activated for admin sessions",
            "SIEM real-time alerting rule tuned and active",
        ],
        "risk_multiplier_range": (0.70, 0.88),
    },
    {
        "event_type": "ransomware_indicator",
        "severities": ["Critical"],
        "descriptions": [
            "Canary file modification alert triggered on storage volume",
            "Rapid file encryption heuristics flagged by endpoint protection",
            "Shadow copy deletion command intercepted",
        ],
        "risk_multiplier_range": (1.20, 1.45),
    },
]


def generate_live_event() -> dict:
    """Generate a single realistic real-time security event with incremental risk delta."""
    state = _load_initial_asset_risk()
    if not state:
        # Fallback dummy assets if state is empty
        asset_ids = [f"AST-{1000 + i}" for i in range(20)]
        for aid in asset_ids:
            state[aid] = {
                "asset_id": aid,
                "business_unit": random.choice(["Finance", "Engineering", "HR", "Sales", "Operations"]),
                "criticality": random.randint(1, 5),
                "EAL_usd": random.uniform(5000, 85000),
                "VaR95_usd": random.uniform(15000, 250000),
                "VaR99_usd": random.uniform(25000, 450000),
                "priority_score": random.uniform(3000, 60000),
            }

    asset_id = random.choice(list(state.keys()))
    current_asset = state[asset_id]

    template = random.choice(EVENT_TEMPLATES)
    severity = random.choice(template["severities"])
    description = random.choice(template["descriptions"])

    # Compute incremental risk change
    low_mult, high_mult = template["risk_multiplier_range"]
    mult = random.uniform(low_mult, high_mult)

    old_eal = current_asset["EAL_usd"]
    new_eal = round(old_eal * mult, 2)
    # Constrain to realistic boundaries ($100 to $1,000,000)
    new_eal = max(100.0, min(new_eal, 1000000.0))

    delta_eal = round(new_eal - old_eal, 2)
    delta_pct = round(((new_eal - old_eal) / max(old_eal, 1.0)) * 100, 1)

    new_var95 = round(current_asset["VaR95_usd"] * mult, 2)
    new_var99 = round(current_asset["VaR99_usd"] * mult, 2)
    new_priority = round(new_eal * (current_asset["criticality"] / 5.0), 2)

    # Update in-memory state
    current_asset["EAL_usd"] = new_eal
    current_asset["VaR95_usd"] = new_var95
    current_asset["VaR99_usd"] = new_var99
    current_asset["priority_score"] = new_priority

    event = {
        "event_id": f"LIVE-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now().isoformat(),
        "asset_id": asset_id,
        "business_unit": current_asset["business_unit"],
        "criticality": current_asset["criticality"],
        "event_type": template["event_type"],
        "severity": severity,
        "description": description,
        "impact": {
            "old_eal_usd": old_eal,
            "new_eal_usd": new_eal,
            "delta_eal_usd": delta_eal,
            "delta_pct": delta_pct,
            "new_var95_usd": new_var95,
            "new_priority_score": new_priority,
        },
    }

    _event_history.insert(0, event)
    if len(_event_history) > MAX_EVENT_HISTORY:
        _event_history.pop()

    return event


@router.get("/api/live-feed/recent")
def get_recent_events():
    """Returns recent streamed threat events for initial load or polling fallback."""
    if not _event_history:
        # Pre-seed a few events
        for _ in range(5):
            generate_live_event()
    return {
        "events": _event_history[:20],
        "total_tracked": len(_event_history),
    }


@router.websocket("/ws/live-feed")
async def live_feed_websocket(websocket: WebSocket):
    """
    WebSocket streaming endpoint emitting simulated live enterprise threat telemetry
    and incremental per-asset FAIR risk re-computations every 3-8 seconds.
    """
    await websocket.accept()
    logger.info("Live threat feed WebSocket client connected.")

    # Send initial welcome message and initial recent events
    initial_event = generate_live_event()
    await websocket.send_text(
        json.dumps({
            "type": "INITIAL_STATE",
            "recent_events": _event_history[:10],
            "latest_event": initial_event,
        })
    )

    try:
        while True:
            # Interval between 3 to 8 seconds
            delay = random.uniform(3.5, 7.5)
            await asyncio.sleep(delay)

            event = generate_live_event()
            message = {
                "type": "THREAT_EVENT",
                "event": event,
            }
            await websocket.send_text(json.dumps(message))
    except WebSocketDisconnect:
        logger.info("Live threat feed WebSocket client disconnected gracefully.")
    except asyncio.CancelledError:
        logger.info("Live threat feed WebSocket task cancelled.")
    except Exception as e:
        logger.warning(f"Error in live feed WebSocket stream: {e}")
