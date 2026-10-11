"""Current server-side authority; JWT role/permission claims are never authority."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.rls import clear_rls_context, set_actor_context, set_platform_context, set_rls_context
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.session import AuthSession
from app.models.user import User


def denied() -> HTTPException:
    return HTTPException(status_code=401, detail="Session or organization access is unavailable")


def load_identity(db: Session, user_id: str) -> User:
    # Narrow authentication bootstrap: lookup ONLY the signed subject, never expose
    # a tenant query while bypass is active. No autoflush of client/route mutations.
    try:
        with db.no_autoflush:
            set_platform_context(db)
            user = db.execute(
                select(User).where(User.id == user_id).execution_options(populate_existing=True)
            ).scalar_one_or_none()
            if not user or not user.is_active or user.status != "active":
                raise denied()
            return user
    finally:
        clear_rls_context(db)


def resolve_authority(db: Session, user: User, org_id: int) -> dict:
    if not isinstance(org_id, int) or isinstance(org_id, bool) or org_id <= 0:
        raise denied()
    set_rls_context(db, org_id)
    org = db.execute(
        select(Organization).where(Organization.id == org_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if not org or org.status != "active":
        raise denied()
    if user.is_platform_admin:
        # Platform privilege comes only from the current persisted user flag.
        set_platform_context(db)
        role, category_scope = "platform_admin", None
    else:
        membership = db.execute(
            select(Membership).where(Membership.user_id == user.id, Membership.org_id == org_id)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if not membership or membership.status != "active":
            raise denied()
        # Never let a tenant membership fabricate a platform role/privilege.
        if membership.role == "platform_admin":
            raise denied()
        role, category_scope = membership.role, membership.category_scope
    from app.core.permissions import resolve_permissions
    set_actor_context(db, user.id, role)
    return {
        "id": user.id, "username": user.username, "email": user.email,
        "full_name": user.full_name, "role": role, "category_scope": category_scope,
        "org_id": org_id, "is_platform_admin": bool(user.is_platform_admin),
        "permissions": resolve_permissions(role, bool(user.is_platform_admin), category_scope, org_id, db),
        "theme_preference": user.theme_preference or "system",
    }


def require_live_session(db: Session, user_id: str, org_id: int, session_id: str) -> AuthSession:
    if not isinstance(session_id, str) or not session_id:
        raise denied()
    session = db.execute(
        select(AuthSession).where(
            AuthSession.id == session_id, AuthSession.user_id == user_id,
            AuthSession.org_id == org_id, AuthSession.revoked_at.is_(None),
        ).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if not session:
        raise denied()
    try:
        expiry = datetime.fromisoformat(session.expires_at).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        raise denied() from None
    if expiry <= datetime.now(UTC):
        raise denied()
    return session


def authenticate_payload(db: Session, payload: dict) -> tuple[dict, AuthSession]:
    subject, org_id = payload.get("sub"), payload.get("org_id")
    if not isinstance(subject, str) or not subject:
        raise denied()
    user = load_identity(db, subject)
    authority = resolve_authority(db, user, org_id)
    session = require_live_session(db, user.id, org_id, payload.get("sid"))
    return authority, session
