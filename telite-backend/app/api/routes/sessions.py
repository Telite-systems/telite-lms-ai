"""
Session management API — Phase 4.

Provides endpoints for:
- Listing all active sessions for the current user (device tracking)
- Revoking a specific session (remote logout)
- Revoking all sessions (security lockout)
- Account switcher: list available accounts

This enables Slack/Google-style multi-account switching where a user
can be logged into multiple organisations simultaneously.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import (
    TokenData,
    _account_refresh_cookie_name,
    _build_token_response,
    _clear_auth_cookies,
    _set_auth_cookies,
    get_current_user,
    issue_login_response,
    require_platform_admin,
    validate_auth_cookie_mutation,
)
from app.core.security import generate_csrf_token
from app.db.engine import db_session
from app.repositories.auth_repo import AuthRepository

logger = logging.getLogger("telite.sessions")

sessions_router = APIRouter(prefix="/auth/sessions", tags=["Sessions"], dependencies=[Depends(validate_auth_cookie_mutation)])


# ── Pydantic models ───────────────────────────────────────────────────────────

class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    expires_at: str
    is_current: bool
    user_agent: str | None = None
    ip_address: str | None = None


class SwitchAccountRequest(BaseModel):
    """Request to switch to a different org context for the same user."""
    target_org_id: int


class AddAccountRequest(BaseModel):
    """Add a second account (different user) to the browser session."""
    username: str
    password: str


class SwitchBrowserAccountRequest(BaseModel):
    """Switch to another browser-linked account without exposing refresh tokens to JS."""
    target_user_id: str


# ── Session listing ───────────────────────────────────────────────────────────

@sessions_router.get("/", response_model=list[SessionInfo])
def list_sessions(
    current_user: TokenData = Depends(get_current_user),
    cookie_refresh: str | None = Cookie(default=None, alias="telite_refresh_token"),
    db: Session = Depends(db_session),
) -> list[SessionInfo]:
    """
    List all active sessions for the current user.
    Marks the current session so the UI can show 'This device'.
    """
    auth_repo = AuthRepository(db)
    sessions = auth_repo.list_active_sessions(current_user.id)

    result = []
    for s in sessions:
        is_current = (
            s.id == current_user.session_id
        )
        result.append(
            SessionInfo(
                session_id=s.id,
                created_at=s.created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(s.created_at, datetime) else str(s.created_at),
                expires_at=s.expires_at,
                is_current=is_current,
                user_agent=s.user_agent,
                ip_address=s.ip_address,
            )
        )

    return result


# ── Session revocation ────────────────────────────────────────────────────────

@sessions_router.delete("/{session_id}")
def revoke_one_session(
    session_id: str,
    response: Response,
    current_user: TokenData = Depends(get_current_user),
    cookie_refresh: str | None = Cookie(default=None, alias="telite_refresh_token"),
    db: Session = Depends(db_session),
) -> dict[str, str]:
    """
    Revoke a specific session by ID.
    If revoking the current session, also clears cookies.
    """
    auth_repo = AuthRepository(db)
    session = auth_repo.get_by_id(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Users can only revoke their own sessions
    if session.user_id != current_user.id and not current_user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Cannot revoke another user's session")

    session.revoked_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    db.commit()

    # If revoking current session, clear cookies too
    is_current = cookie_refresh and session.refresh_token == cookie_refresh
    if is_current:
        _clear_auth_cookies(response)

    logger.info("Session %s revoked by user %s", session_id, current_user.id)
    return {"status": "revoked", "session_id": session_id}


@sessions_router.delete("/")
def revoke_all_sessions(
    response: Response,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Revoke ALL sessions for the current user (security lockout).
    Clears cookies and forces re-login on all devices.
    """
    auth_repo = AuthRepository(db)
    count = auth_repo.revoke_all_for_user(current_user.id)
    db.commit()
    _clear_auth_cookies(response)

    logger.info("All %d sessions revoked for user %s", count, current_user.id)
    return {
        "status": "all_sessions_revoked",
        "count": count,
        "user_id": current_user.id,
    }


# ── Account switcher ──────────────────────────────────────────────────────────

@sessions_router.post("/switch-org")
def switch_org_context(
    body: SwitchAccountRequest,
    response: Response,
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Switch the current user's active org context.
    """
    from app.services.authorization_service import load_identity
    user = load_identity(db, current_user.id)
    token_response = issue_login_response(db, user, response, request, org_id=body.target_org_id)
    return {
        "status": "org_switched", "user_id": user.id, "org_id": token_response.org_id,
        "role": token_response.role, "permissions": token_response.permissions,
    }


@sessions_router.post("/add-account")
def add_account(
    body: AddAccountRequest,
    response: Response,
    request: Request,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Add a second account to the browser session (multi-account switcher).
    """
    from app.api.auth import authenticate_user
    user = authenticate_user(db, body.username, body.password)

    token_response = issue_login_response(db, user, response, request)

    logger.info("Account added to browser session: user=%s", user.id)

    return {
        "status": "account_added",
        "user_id": user.id,
        "role": user.role,
        "name": user.full_name,
        "email": user.email,
        "org_id": user.org_id,
        "is_platform_admin": bool(user.is_platform_admin),
        "permissions": token_response.permissions,
    }


@sessions_router.post("/switch-account")
def switch_browser_account(
    body: SwitchBrowserAccountRequest,
    response: Response,
    request: Request,
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Switch to a browser-linked account using its HttpOnly account refresh cookie.
    """
    cookie_name = _account_refresh_cookie_name(body.target_user_id)
    refresh_token = request.cookies.get(cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account session is not available on this browser. Add the account again.",
        )

    from app.core.security import decode_token
    from app.services.authorization_service import authenticate_payload, denied
    payload = decode_token(refresh_token, token_type="refresh")
    if payload.get("sub") != body.target_user_id:
        raise denied()
    authority, session = authenticate_payload(db, payload)
    if session.refresh_token != refresh_token:
        raise denied()
    token_response = _build_token_response(authority, refresh_token, db=db, session_id=session.id)
    _set_auth_cookies(response, token_response.access_token, refresh_token,
                      generate_csrf_token(), account_user_id=authority["id"])
    return {
        "status": "account_switched", "user_id": authority["id"], "role": authority["role"],
        "name": authority["full_name"], "email": authority["email"],
        "category_scope": authority["category_scope"], "org_id": authority["org_id"],
        "is_platform_admin": authority["is_platform_admin"], "permissions": authority["permissions"],
    }


# ── Platform admin: revoke any user's sessions ────────────────────────────────

@sessions_router.delete("/admin/{user_id}")
def admin_revoke_user_sessions(
    user_id: str,
    response: Response,
    current_user: TokenData = Depends(require_platform_admin),
    db: Session = Depends(db_session),
) -> dict[str, Any]:
    """
    Platform admin: revoke all sessions for any user.
    Used for security incidents or account suspension.
    """
    auth_repo = AuthRepository(db)
    count = auth_repo.revoke_all_for_user(user_id)
    db.commit()
    logger.warning(
        "Platform admin %s revoked all sessions for user %s (%d sessions)",
        current_user.id,
        user_id,
        count,
    )
    return {
        "status": "sessions_revoked",
        "target_user_id": user_id,
        "count": count,
        "revoked_by": current_user.id,
    }
