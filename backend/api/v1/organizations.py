from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.dependencies import get_current_org, get_current_user, require_role
from core.errors import ConflictError, PermissionDeniedError, ResourceNotFoundError
from core.security import generate_secure_token, hash_password
from db.models import Membership, Organization, User
from db.session import get_db
from services.audit import AuditService

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    default_currency: Optional[str] = None
    risk_appetite_thresholds: Optional[Dict[str, float]] = None


class MemberInviteRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "analyst"  # owner, admin, analyst, viewer


class MemberRoleUpdateRequest(BaseModel):
    role: str


@router.get("/current")
def get_current_organization(
    current_org: Organization = Depends(get_current_org),
):
    return {
        "id": current_org.id,
        "name": current_org.name,
        "default_currency": current_org.default_currency,
        "risk_appetite_thresholds": current_org.risk_appetite_thresholds,
        "policy_version": current_org.policy_version,
        "created_at": current_org.created_at.isoformat(),
        "updated_at": current_org.updated_at.isoformat(),
    }


@router.patch("/current")
def update_current_organization(
    payload: OrgUpdateRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Updates organization settings (admin/owner only)."""
    if payload.name is not None:
        current_org.name = payload.name.strip()
    if payload.default_currency is not None:
        current_org.default_currency = payload.default_currency.upper().strip()
    if payload.risk_appetite_thresholds is not None:
        current_org.risk_appetite_thresholds = payload.risk_appetite_thresholds
        current_org.policy_version += 1

    db.commit()
    db.refresh(current_org)
    return current_org


@router.get("/current/members")
def list_members(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    memberships = db.scalars(
        select(Membership).where(Membership.organization_id == current_org.id)
    ).all()

    results = []
    for m in memberships:
        u = db.scalars(select(User).where(User.id == m.user_id)).first()
        if u:
            results.append({
                "user_id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "role": m.role,
                "joined_at": m.created_at.isoformat(),
            })
    return results


@router.post("/current/invitations", status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: MemberInviteRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Invites/adds a member to the organization with a designated role."""
    norm_email = payload.email.strip().lower()
    user = db.scalars(select(User).where(User.email == norm_email)).first()
    if not user:
        # Create user with initial temporary random password
        temp_pwd = generate_secure_token(16)
        user = User(
            email=norm_email,
            password_hash=hash_password(temp_pwd),
            full_name=payload.full_name.strip(),
            is_active=True,
            is_locked=False,
        )
        db.add(user)
        db.flush()

    existing_membership = db.scalars(
        select(Membership).where(
            Membership.organization_id == current_org.id,
            Membership.user_id == user.id,
        )
    ).first()

    if existing_membership:
        raise ConflictError(message="User is already a member of this organization")

    membership = Membership(
        organization_id=current_org.id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()

    return {
        "status": "success",
        "user_id": user.id,
        "email": user.email,
        "role": membership.role,
    }


@router.patch("/current/members/{user_id}")
def update_member_role(
    user_id: str,
    payload: MemberRoleUpdateRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Updates a member's role (admin/owner only). Cannot change own role."""
    if user_id == current_user.id:
        raise PermissionDeniedError(message="Cannot modify your own role")

    membership = db.scalars(
        select(Membership).where(
            Membership.organization_id == current_org.id,
            Membership.user_id == user_id,
        )
    ).first()

    if not membership:
        raise ResourceNotFoundError(message="Member not found in this organization")

    membership.role = payload.role
    db.commit()
    return {"status": "success", "user_id": user_id, "new_role": payload.role}
