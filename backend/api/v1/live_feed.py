import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, require_dataset_access
from core.errors import ResourceNotFoundError
from core.security import decode_access_token
from db.models import (
    Dataset,
    DatasetVersion,
    Membership,
    Organization,
    ThreatEvent,
    User,
)
from db.session import get_db, SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["live-feed"])

WS_UNAUTHORIZED = 4401
WS_NOT_FOUND = 4404


def _resolve_org_dataset_ids(db: Session, org_id: str) -> List[str]:
    return [d.id for d in db.scalars(select(Dataset).where(Dataset.organization_id == org_id)).all()]


@router.get("/live-feed/recent")
def get_recent_live_feed(
    dataset_id: Optional[str] = Query(None),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """
    Returns recent threat events. Prioritizes real observed events from dataset telemetry.
    If no events exist, falls back to clearly labeled 'synthetic_demo' events.

    Events are strictly scoped to datasets owned by the authenticated organization.
    """
    dataset_ids = _resolve_org_dataset_ids(db, current_org.id)

    if dataset_id:
        if dataset_id not in dataset_ids:
            raise ResourceNotFoundError(message=f"Dataset '{dataset_id}' not found in this organization")
        dataset = db.scalars(select(Dataset).where(Dataset.id == dataset_id)).first()
        version_ids = [dataset.active_version_id] if dataset and dataset.active_version_id else []
        if not version_ids:
            version_ids = [
                v.id
                for v in db.scalars(
                    select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
                ).all()
            ]
        query = select(ThreatEvent).where(ThreatEvent.dataset_version_id.in_(version_ids))
    else:
        version_ids = [
            v.id
            for v in db.scalars(
                select(DatasetVersion).where(DatasetVersion.dataset_id.in_(dataset_ids))
            ).all()
        ] if dataset_ids else []
        if not version_ids:
            return {"source_type": "synthetic_demo", "events": _demo_events()}
        query = select(ThreatEvent).where(ThreatEvent.dataset_version_id.in_(version_ids))

    events = db.scalars(query.order_by(ThreatEvent.observed_at.desc()).limit(20)).all()

    if events:
        event_source_types = {e.source_type for e in events}
        if event_source_types == {"observed"}:
            feed_source = "observed"
        elif event_source_types == {"synthetic_demo"}:
            feed_source = "synthetic_demo"
        else:
            feed_source = "mixed"
        return {
            "source_type": feed_source,
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.observed_at.isoformat(),
                    "asset_id": e.asset_id,
                    "mitre_technique_id": e.mitre_technique_id,
                    "description": e.description,
                    "severity": e.severity,
                    "action_taken": e.action_taken,
                    "source_type": e.source_type,
                }
                for e in events
            ],
        }

    return {"source_type": "synthetic_demo", "events": _demo_events()}


def _demo_events() -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    return [
        {
            "event_id": f"DEMO-{uuid.uuid4().hex[:6].upper()}",
            "timestamp": now.isoformat(),
            "asset_id": "AST-1001",
            "mitre_technique_id": "T1110.001",
            "description": "Password Guessing probe blocked by perimeter firewall",
            "severity": "Medium",
            "action_taken": "blocked",
            "source_type": "synthetic_demo",
        },
        {
            "event_id": f"DEMO-{uuid.uuid4().hex[:6].upper()}",
            "timestamp": now.isoformat(),
            "asset_id": "AST-1002",
            "mitre_technique_id": "T1190",
            "description": "Exploit Public-Facing Application attempt intercepted by WAF",
            "severity": "High",
            "action_taken": "blocked",
            "source_type": "synthetic_demo",
        },
    ]


def _authenticate_ws_token(db: Session, token: Optional[str], dataset_id: Optional[str]) -> Organization:
    """
    Validates a websocket access token and dataset scope.
    Raises ValueError with a close code on failure.
    """
    if not token:
        raise _WsAuthError(WS_UNAUTHORIZED, "Access token required for live feed")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise _WsAuthError(WS_UNAUTHORIZED, "Invalid or expired access token")

    user_id = payload.get("sub")
    org_id = payload.get("org_id")
    if not user_id or not org_id:
        raise _WsAuthError(WS_UNAUTHORIZED, "Malformed access token")

    user = db.scalars(select(User).where(User.id == user_id)).first()
    if not user or not user.is_active or user.is_locked:
        raise _WsAuthError(WS_UNAUTHORIZED, "Account inactive")

    membership = db.scalars(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == org_id,
        )
    ).first()
    if not membership:
        raise _WsAuthError(WS_UNAUTHORIZED, "Not a member of the requested organization")

    org = db.scalars(select(Organization).where(Organization.id == org_id)).first()
    if not org:
        raise _WsAuthError(WS_UNAUTHORIZED, "Organization not found")

    if dataset_id:
        owns = db.scalars(
            select(Dataset).where(
                Dataset.id == dataset_id,
                Dataset.organization_id == org_id,
            )
        ).first()
        if not owns:
            raise _WsAuthError(WS_NOT_FOUND, "Dataset not found in this organization")

    return org


class _WsAuthError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@router.websocket("/ws/live-feed")
async def live_feed_websocket(websocket: WebSocket, dataset_id: Optional[str] = None, token: Optional[str] = None):
    """
    Authenticated WebSocket streaming endpoint. Emits observed security events or
    clearly labeled synthetic demo events. Connections without a valid token that
    authorizes the requested dataset are closed.
    """
    db: Session = SessionLocal()
    try:
        try:
            _authenticate_ws_token(db, token, dataset_id)
        except _WsAuthError as exc:
            await websocket.close(code=exc.code, reason=exc.message)
            return
    finally:
        db.close()

    await websocket.accept()
    logger.info("WebSocket live feed connected for dataset %s", dataset_id)

    try:
        while True:
            await asyncio.sleep(random.uniform(4.0, 8.0))
            now = datetime.now(timezone.utc)
            event_payload = {
                "type": "THREAT_EVENT",
                "event": {
                    "event_id": f"FEED-{uuid.uuid4().hex[:6].upper()}",
                    "timestamp": now.isoformat(),
                    "asset_id": f"AST-{random.randint(1001, 1010)}",
                    "severity": random.choice(["Critical", "High", "Medium"]),
                    "description": "Simulated security telemetry event",
                    "source_type": "synthetic_demo",
                },
            }
            await websocket.send_text(json.dumps(event_payload))
    except WebSocketDisconnect:
        logger.info("WebSocket live feed disconnected.")
    except Exception as e:
        logger.warning("WebSocket live feed exception: %s", str(e))
