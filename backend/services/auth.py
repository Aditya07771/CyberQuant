import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.errors import AuthenticationError, ConflictError, PermissionDeniedError, ResourceNotFoundError
from core.security import (
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)
from db.models import Membership, Organization, RefreshSession, User, RiskPolicy


ROLE_HIERARCHY = {
    "viewer": 1,
    "analyst": 2,
    "admin": 3,
    "owner": 4,
}


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        organization_name: str,
    ) -> Tuple[User, Organization, str, str]:
        """Registers a new user, creates their primary organization, and sets role to 'owner'."""
        normalized_email = email.strip().lower()

        # Check existing user
        existing_user = self.db.scalars(
            select(User).where(User.email == normalized_email)
        ).first()
        if existing_user:
            raise ConflictError(message="A user with this email address already exists")

        # Create User
        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            is_active=True,
            is_locked=False,
        )
        self.db.add(user)
        self.db.flush()

        # Create Organization
        org = Organization(
            name=organization_name.strip(),
            default_currency="USD",
            policy_version=1,
            risk_appetite_thresholds={
                "max_eal_usd": 1_000_000.0,
                "max_var95_usd": 3_000_000.0,
                "max_cvar95_usd": 5_000_000.0,
            },
        )
        self.db.add(org)
        self.db.flush()

        # Assign 'owner' membership
        membership = Membership(
            organization_id=org.id,
            user_id=user.id,
            role="owner",
        )
        self.db.add(membership)

        # Create default risk policy
        policy = RiskPolicy(
            organization_id=org.id,
            version=1,
            max_eal_threshold_usd=1_000_000.0,
            max_var95_threshold_usd=3_000_000.0,
            max_cvar95_threshold_usd=5_000_000.0,
            remediation_sla_critical_days=7,
            remediation_sla_high_days=30,
            deduplication_window_hours=24,
            notify_email_recipients=[],
            notify_webhook_urls=[],
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(org)

        # Create initial access and refresh tokens
        access_token, refresh_token = self.create_tokens(user.id, org.id)
        return user, org, access_token, refresh_token

    def login(
        self,
        email: str,
        password: str,
        organization_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, Organization, str, str]:
        """Authenticates a user and issues access + refresh tokens."""
        normalized_email = email.strip().lower()
        user = self.db.scalars(
            select(User).where(User.email == normalized_email)
        ).first()

        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError(message="Invalid email or password")

        if not user.is_active or user.is_locked:
            raise AuthenticationError(message="Account is inactive or locked")

        # Resolve organization
        membership = None
        if organization_id:
            membership = self.db.scalars(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == organization_id,
                )
            ).first()
            if not membership:
                raise PermissionDeniedError(message="Not a member of the requested organization")
        else:
            membership = self.db.scalars(
                select(Membership).where(Membership.user_id == user.id)
            ).first()
            if not membership:
                raise PermissionDeniedError(message="User has no organization memberships")

        org = self.db.scalars(
            select(Organization).where(Organization.id == membership.organization_id)
        ).first()

        access_token, refresh_token = self.create_tokens(
            user.id, org.id, user_agent=user_agent, ip_address=ip_address
        )
        return user, org, access_token, refresh_token

    def create_tokens(
        self,
        user_id: str,
        org_id: str,
        family_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Creates access and refresh tokens and stores session record."""
        access_token = create_access_token({"sub": user_id, "org_id": org_id})
        raw_refresh_token = generate_secure_token(48)
        hashed_refresh_token = hash_token(raw_refresh_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        session = RefreshSession(
            user_id=user_id,
            organization_id=org_id,
            refresh_token_hash=hashed_refresh_token,
            family_id=family_id or str(uuid.uuid4()),
            is_revoked=False,
            expires_at=expires_at,
            created_at=now,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(session)
        self.db.commit()

        return access_token, raw_refresh_token

    def refresh_tokens(
        self,
        refresh_token_plain: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Rotates refresh token. Detects token reuse; if a reused token is presented,
        revokes the entire session family for security.
        Returns: (access_token, new_refresh_token, org_id)
        """
        token_hash = hash_token(refresh_token_plain)
        session = self.db.scalars(
            select(RefreshSession).where(RefreshSession.refresh_token_hash == token_hash)
        ).first()

        if not session:
            raise AuthenticationError(message="Invalid refresh token")

        # Check reuse detection
        if session.is_revoked or session.rotated_at is not None:
            # Token reuse detected! Revoke all sessions in the same family
            family_sessions = self.db.scalars(
                select(RefreshSession).where(RefreshSession.family_id == session.family_id)
            ).all()
            for s in family_sessions:
                s.is_revoked = True
            self.db.commit()
            raise AuthenticationError(message="Refresh token reuse detected. All related sessions have been revoked.")

        now = datetime.now(timezone.utc)
        # Handle naive or aware datetimes from DB
        sess_expires_at = session.expires_at
        if sess_expires_at.tzinfo is None:
            sess_expires_at = sess_expires_at.replace(tzinfo=timezone.utc)

        if sess_expires_at < now:
            session.is_revoked = True
            self.db.commit()
            raise AuthenticationError(message="Refresh token expired")

        # Mark previous session as rotated
        session.rotated_at = now
        session.is_revoked = True
        self.db.commit()

        # Create new tokens under same family
        access_token, new_refresh_token = self.create_tokens(
            user_id=session.user_id,
            org_id=session.organization_id,
            family_id=session.family_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return access_token, new_refresh_token, session.organization_id

    def logout(self, refresh_token_plain: str) -> None:
        """Revokes the refresh session."""
        token_hash = hash_token(refresh_token_plain)
        session = self.db.scalars(
            select(RefreshSession).where(RefreshSession.refresh_token_hash == token_hash)
        ).first()
        if session:
            session.is_revoked = True
            self.db.commit()
