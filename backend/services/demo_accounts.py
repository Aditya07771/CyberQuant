"""Pre-seeded demo accounts for one-click login.

These are intentionally public demo credentials for local demos only. They are
gated behind the ``ENABLE_DEMO_LOGIN`` setting and must never be enabled on a
production deployment.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Membership, Organization, User
from services.auth import AuthService

# Public, non-secret demo credentials. Passwords are only used to (re)create the
# account when it is missing; they are never surfaced as authoritative secrets.
DEMO_ACCOUNTS: List[Dict[str, Any]] = [
    {
        "key": "northwind",
        "label": "Northwind Bank",
        "blurb": "Financial services · high regulatory exposure",
        "email": "demo.northwind@cyberquant.local",
        "password": "Demo!Passw0rd1",
        "full_name": "Nadia Northwind",
        "organization_name": "Northwind Bank",
    },
    {
        "key": "acmehealth",
        "label": "Acme Health",
        "blurb": "Healthcare · patient data sensitivity",
        "email": "demo.acmehealth@cyberquant.local",
        "password": "Demo!Passw0rd2",
        "full_name": "Adam Acme",
        "organization_name": "Acme Health",
    },
    {
        "key": "globex",
        "label": "Globex Manufacturing",
        "blurb": "Industrial · OT/IT dependency risk",
        "email": "demo.globex@cyberquant.local",
        "password": "Demo!Passw0rd3",
        "full_name": "Grace Globex",
        "organization_name": "Globex Manufacturing",
    },
]

_BY_KEY = {a["key"]: a for a in DEMO_ACCOUNTS}
_BY_EMAIL = {a["email"]: a for a in DEMO_ACCOUNTS}


def public_accounts() -> List[Dict[str, str]]:
    """Returns the demo account metadata safe to expose to the frontend."""
    return [
        {
            "key": a["key"],
            "label": a["label"],
            "blurb": a["blurb"],
            "email": a["email"],
            "organization_name": a["organization_name"],
        }
        for a in DEMO_ACCOUNTS
    ]


def resolve_spec(key: Optional[str] = None, email: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if key:
        return _BY_KEY.get(key)
    if email:
        return _BY_EMAIL.get(email.strip().lower())
    return None


def ensure_demo_account(db: Session, spec: Dict[str, Any]) -> Tuple[User, Organization]:
    """Creates the demo user + organization if absent; otherwise returns them."""
    existing = db.scalars(select(User).where(User.email == spec["email"])).first()
    if existing:
        membership = db.scalars(
            select(Membership).where(Membership.user_id == existing.id)
        ).first()
        org = None
        if membership:
            org = db.scalars(
                select(Organization).where(Organization.id == membership.organization_id)
            ).first()
        if org:
            return existing, org

    service = AuthService(db)
    user, org, _access, _refresh = service.register(
        email=spec["email"],
        password=spec["password"],
        full_name=spec["full_name"],
        organization_name=spec["organization_name"],
    )
    return user, org
