from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_org, get_current_user
from core.errors import BadInputError, ResourceNotFoundError
from db.models import Organization, User
from db.session import get_db
from services import demo_accounts
from services.audit import AuditService
from services.auth import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    organization_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Registers a new user, primary organization, and assigns 'owner' role."""
    auth_service = AuthService(db)
    user, org, access_token, refresh_token = auth_service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        organization_name=payload.organization_name,
    )

    AuditService.log(
        db=db,
        org_id=org.id,
        actor_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": "success",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "default_currency": org.default_currency,
            "role": "owner",
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticates user credentials and issues access + refresh tokens."""
    auth_service = AuthService(db)
    user_agent = request.headers.get("user-agent")
    ip_addr = request.client.host if request.client else None

    user, org, access_token, refresh_token = auth_service.login(
        email=payload.email,
        password=payload.password,
        organization_id=payload.organization_id,
        user_agent=user_agent,
        ip_address=ip_addr,
    )

    AuditService.log(
        db=db,
        org_id=org.id,
        actor_id=user.id,
        action="user.login",
        resource_type="session",
        request_id=getattr(request.state, "request_id", None),
        ip_address=ip_addr,
    )

    return {
        "status": "success",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "default_currency": org.default_currency,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/refresh")
def refresh_token(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Rotates refresh token and returns a new access/refresh pair with token reuse detection."""
    auth_service = AuthService(db)
    user_agent = request.headers.get("user-agent")
    ip_addr = request.client.host if request.client else None

    access_token, new_refresh_token, org_id = auth_service.refresh_tokens(
        refresh_token_plain=payload.refresh_token,
        user_agent=user_agent,
        ip_address=ip_addr,
    )

    return {
        "status": "success",
        "tokens": {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    """Revokes the refresh session."""
    auth_service = AuthService(db)
    auth_service.logout(payload.refresh_token)
    return None


@router.get("/me")
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Returns profile of authenticated user and their active organization."""
    role = "viewer"
    for m in current_user.memberships:
        if m.organization_id == current_org.id:
            role = m.role
            break

    memberships_info = [
        {"organization_id": m.organization_id, "role": m.role}
        for m in current_user.memberships
    ]

    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
        },
        "active_organization": {
            "id": current_org.id,
            "name": current_org.name,
            "default_currency": current_org.default_currency,
            "role": role,
        },
        "memberships": memberships_info,
    }


# ---------------------------------------------------------------------------
# One-click demo login (gated behind ENABLE_DEMO_LOGIN)
# ---------------------------------------------------------------------------

class DemoLoginRequest(BaseModel):
    key: Optional[str] = None
    email: Optional[str] = None


def _require_demo_login_enabled() -> None:
    if not settings.ENABLE_DEMO_LOGIN:
        raise ResourceNotFoundError(message="Demo login is disabled")


def _auth_payload(user: User, org: Organization, access_token: str, refresh_token: str) -> Dict[str, Any]:
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        },
        "organization": {
            "id": org.id,
            "name": org.name,
            "default_currency": org.default_currency,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.get("/demo-accounts")
def list_demo_accounts():
    """Lists the pre-seeded demo organizations available for one-click login."""
    _require_demo_login_enabled()
    return demo_accounts.public_accounts()


@router.post("/demo-login")
def demo_login(payload: DemoLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Signs in to a pre-seeded demo organization, creating it on first use."""
    _require_demo_login_enabled()

    spec = demo_accounts.resolve_spec(key=payload.key, email=payload.email)
    if not spec:
        raise BadInputError(message="Unknown demo account")

    demo_accounts.ensure_demo_account(db, spec)

    auth_service = AuthService(db)
    user, org, access_token, refresh_token = auth_service.login(
        email=spec["email"],
        password=spec["password"],
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    AuditService.log(
        db=db,
        org_id=org.id,
        actor_id=user.id,
        action="user.demo_login",
        resource_type="session",
        request_id=getattr(request.state, "request_id", None),
    )

    return _auth_payload(user, org, access_token, refresh_token)
