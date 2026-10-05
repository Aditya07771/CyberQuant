from typing import Callable, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import AuthenticationError, PermissionDeniedError, ResourceNotFoundError
from core.security import decode_access_token
from db.models import Dataset, Membership, Organization, RiskRun, User
from db.session import get_db
from services.auth import ROLE_HIERARCHY

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Validates the Bearer token and returns the authenticated User."""
    if not credentials or not credentials.credentials:
        raise AuthenticationError(message="Bearer token required")

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise AuthenticationError(message="Invalid or expired access token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError(message="Malformed access token")

    user = db.scalars(select(User).where(User.id == user_id)).first()
    if not user or not user.is_active or user.is_locked:
        raise AuthenticationError(message="User not found or account inactive")

    return user


def get_current_org(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    current_user: User = Depends(get_current_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: Session = Depends(get_db),
) -> Organization:
    """
    Resolves the active organization for the user.
    Checks token 'org_id', header 'X-Organization-Id', or falls back to first membership.
    Enforces that user is actually a member of the organization.
    """
    target_org_id = None
    if credentials and credentials.credentials:
        try:
            payload = decode_access_token(credentials.credentials)
            target_org_id = payload.get("org_id")
        except Exception:
            pass

    if x_organization_id:
        target_org_id = x_organization_id

    # Verify membership
    query = select(Membership).where(Membership.user_id == current_user.id)
    if target_org_id:
        query = query.where(Membership.organization_id == target_org_id)

    membership = db.scalars(query).first()
    if not membership:
        raise PermissionDeniedError(message="You are not a member of the requested organization")

    org = db.scalars(select(Organization).where(Organization.id == membership.organization_id)).first()
    if not org:
        raise ResourceNotFoundError(message="Organization not found")

    # Attach effective role to request state
    request.state.current_user = current_user
    request.state.current_org = org
    request.state.current_role = membership.role

    return org


def require_role(min_role: str) -> Callable:
    """Dependency factory checking that user's effective role meets or exceeds min_role."""
    min_rank = ROLE_HIERARCHY.get(min_role, 1)

    def role_checker(
        request: Request,
        current_org: Organization = Depends(get_current_org),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> str:
        membership = db.scalars(
            select(Membership).where(
                Membership.organization_id == current_org.id,
                Membership.user_id == current_user.id,
            )
        ).first()

        if not membership:
            raise PermissionDeniedError(message="Not a member of this organization")

        user_rank = ROLE_HIERARCHY.get(membership.role, 0)
        if user_rank < min_rank:
            raise PermissionDeniedError(
                message=f"Operation requires '{min_role}' role or higher (current: '{membership.role}')"
            )
        return membership.role

    return role_checker


def require_dataset_access(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_org: Organization = Depends(get_current_org),
) -> Dataset:
    """
    Enforces tenant scoping on dataset access.
    Returns 404 if dataset is not found in the current organization to prevent information leakage.
    """
    dataset = db.scalars(
        select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.organization_id == current_org.id,
        )
    ).first()

    if not dataset:
        raise ResourceNotFoundError(message=f"Dataset '{dataset_id}' not found in this organization")

    return dataset


def require_run_access(
    run_id: str,
    dataset_id: str,
    db: Session = Depends(get_db),
    current_org: Organization = Depends(get_current_org),
) -> RiskRun:
    """
    Enforces tenant and dataset scoping on risk run access.
    Returns 404 if run is not found in the specified dataset and current organization.
    """
    run = db.scalars(
        select(RiskRun).where(
            RiskRun.id == run_id,
            RiskRun.dataset_id == dataset_id,
            RiskRun.organization_id == current_org.id,
        )
    ).first()

    if not run:
        raise ResourceNotFoundError(message=f"Risk run '{run_id}' not found for dataset '{dataset_id}'")

    return run
