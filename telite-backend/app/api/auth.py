"""
Authentication module for Telite LMS.

PHASE 2 SECURITY HARDENING:
- PyJWT replaces custom base64+HMAC implementation
- HttpOnly Secure cookies replace localStorage JWT storage
- CSRF double-submit cookie protection on all mutations
- Redis-backed distributed rate limiting
- Production secret validation (fails hard if not set)
- Refresh token stored in DB and revocable
- No hardcoded secrets or fallback values in production
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.password_utils import verify_password
from app.core.rate_limiter import clear_attempts, is_limited, record_attempt
from app.core.security import (
    create_access_payload,
    create_access_token,
    create_refresh_payload,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    validate_csrf_token,
)
from app.db.engine import db_session
from app.db.rls import clear_rls_context, set_platform_context
from app.repositories.auth_repo import AuthRepository
from app.repositories.user_repo import UserRepository
from app.services.email import send_password_reset_email

# ── Configuration ─────────────────────────────────────────────────────────────

LOGIN_FAILURE_LIMIT = int(os.getenv("TELITE_LOGIN_FAILURE_LIMIT", "5"))
LOGIN_FAILURE_WINDOW_SECONDS = int(os.getenv("TELITE_LOGIN_FAILURE_WINDOW_SECONDS", "300"))
FORGOT_PASSWORD_LIMIT = int(os.getenv("TELITE_FORGOT_PASSWORD_LIMIT", "3"))
FORGOT_PASSWORD_WINDOW_SECONDS = int(os.getenv("TELITE_FORGOT_PASSWORD_WINDOW_SECONDS", "900"))
RESET_PASSWORD_LIMIT = int(os.getenv("TELITE_RESET_PASSWORD_LIMIT", "5"))
RESET_PASSWORD_WINDOW_SECONDS = int(os.getenv("TELITE_RESET_PASSWORD_WINDOW_SECONDS", "900"))
REFRESH_TOKEN_DAYS = int(os.getenv("TELITE_REFRESH_TOKEN_DAYS", "14"))
THEME_PREFERENCES = {"light", "dark", "system"}

# Cookie settings — tighten in production
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")   # "strict" in production
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "") or None   # e.g. ".telite.com"
COOKIE_HTTPONLY = True                                    # always HttpOnly

# Bearer fallback for API clients / Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _client_user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "unknown")[:500]


def _account_refresh_cookie_name(user_id: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:20]
    return f"telite_account_refresh_{digest}"


def _rate_key(namespace: str, raw_value: str) -> str:
    normalized = raw_value.strip().lower() or "unknown"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def _raise_rate_limit(retry_after: int) -> None:
    raise HTTPException(
        status_code=429,
        detail="Too many requests. Please try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    *,
    account_user_id: str | None = None,
) -> None:
    """Set HttpOnly auth cookies and a readable CSRF cookie."""
    access_max_age = int(os.getenv("TELITE_ACCESS_TOKEN_HOURS", "8")) * 3600
    refresh_max_age = REFRESH_TOKEN_DAYS * 86400

    # Access token — HttpOnly, not readable by JS
    response.set_cookie(
        key="telite_access_token",
        value=access_token,
        max_age=access_max_age,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )
    # Refresh token — HttpOnly, only sent to /auth/refresh
    response.set_cookie(
        key="telite_refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        httponly=COOKIE_HTTPONLY,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/auth/refresh",
    )
    if account_user_id and refresh_token:
        response.set_cookie(
            key=_account_refresh_cookie_name(account_user_id),
            value=refresh_token,
            max_age=refresh_max_age,
            httponly=COOKIE_HTTPONLY,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN,
            path="/auth/sessions/switch-account",
        )
    # CSRF token — NOT HttpOnly so JS can read and send it in X-CSRF-Token header
    response.set_cookie(
        key="telite_csrf_token",
        value=csrf_token,
        max_age=access_max_age,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear all auth cookies on logout."""
    for name, path in [
        ("telite_access_token", "/"),
        ("telite_refresh_token", "/auth/refresh"),
        ("telite_csrf_token", "/"),
    ]:
        response.delete_cookie(
            key=name,
            path=path,
            domain=COOKIE_DOMAIN,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
        )


# ── Pydantic models ───────────────────────────────────────────────────────────

class TokenData(BaseModel):
    """
    Decoded JWT payload attached to every authenticated request.
    Phase 4: includes permissions list for fast frontend checks.
    """
    id: str
    username: str | None = None
    email: str
    role: str
    full_name: str
    category_scope: str | None = None
    org_id: int | None = None
    is_platform_admin: bool = False
    permissions: list[str] | None = None
    session_id: str | None = None
    theme_preference: str = "system"

    def has_permission(self, permission: str) -> bool:
        """Fast permission check without DB lookup."""
        from app.core.rbac import has_permission
        return has_permission(self, permission)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str | None = None
    role: str
    name: str
    email: str
    category_scope: str | None = None
    org_id: int | None = None
    is_platform_admin: bool = False
    permissions: list[str] = []
    theme_preference: str = "system"


class RefreshRequest(BaseModel):
    refresh_token: str | None = None   # optional — cookie is preferred


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class ThemePreferenceRequest(BaseModel):
    theme_preference: str


# ── Core auth functions ───────────────────────────────────────────────────────

def authenticate_user(db: Session, identifier: str, password: str):
    repo = UserRepository(db)
    user = repo.get_by_identifier_for_auth(identifier)
    if not user or not user.is_active or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
    cookie_token: str | None = Cookie(default=None, alias="telite_access_token"),
    db: Session = Depends(db_session),
) -> TokenData:
    """
    Resolve the current user from either:
    1. HttpOnly cookie (preferred — browser clients)
    2. Bearer token header (API clients / Swagger)

    Phase 4: permissions list populated from JWT claims.
    """
    bearer = bearer_token.strip() if bearer_token else None
    if bearer and bearer.lower() in {"null", "undefined", "none"}:
        bearer = None

    token = bearer or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not bearer:
        validate_csrf(request, request.cookies.get("telite_csrf_token"), required=True)
    payload = decode_token(token, token_type="access")
    from app.services.authorization_service import authenticate_payload
    authority, session = authenticate_payload(db, payload)
    return TokenData(**authority, session_id=session.id)


def validate_csrf(
    request: Request,
    csrf_cookie: str | None = None,
    *,
    required: bool = False,
) -> None:
    """Cookie-authenticated mutations require a matching double-submit pair."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if not required:
        return
    csrf_cookie = csrf_cookie or request.cookies.get("telite_csrf_token")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not csrf_cookie or not header_token or not validate_csrf_token(header_token, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")


def validate_auth_cookie_mutation(request: Request) -> None:
    # Refresh/switch-account can be authenticated by cookies without an access
    # token. Apply CSRF before those handlers too; no public-login cookie exemption.
    uses_cookie = any(
        name in {"telite_access_token", "telite_refresh_token"}
        or name.startswith("telite_account_refresh_")
        for name in request.cookies
    )
    bearer = request.headers.get("Authorization", "").lower().startswith("bearer ")
    cookie_only_route = request.url.path in {"/auth/refresh", "/auth/sessions/switch-account"}
    validate_csrf(request, required=uses_cookie and (cookie_only_route or not bearer))


# ── Role guards ───────────────────────────────────────────────────────────────

def is_admin_role(role: str) -> bool:
    return role in ("super_admin", "category_admin", "platform_admin")

def is_tenant_super_admin_role(role: str) -> bool:
    return role == "super_admin"


def require_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not current_user.is_platform_admin and not is_admin_role(current_user.role):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_super_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not current_user.is_platform_admin and not is_tenant_super_admin_role(current_user.role):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return current_user


def require_platform_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if not current_user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return current_user


def resolve_org_scope(current_user: TokenData, requested_org_id: int | None = None) -> int | None:
    if current_user.is_platform_admin:
        return requested_org_id if requested_org_id is not None else current_user.org_id
    if current_user.org_id is None:
        raise HTTPException(status_code=403, detail="Organization context is required")
    if requested_org_id is not None and requested_org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="You do not have access to this organization")
    return current_user.org_id


def ensure_org_access(current_user: TokenData, target_org_id: int | None) -> int | None:
    if current_user.is_platform_admin:
        return target_org_id
    if current_user.org_id is None or target_org_id is None or current_user.org_id != target_org_id:
        raise HTTPException(status_code=403, detail="You do not have access to this organization")
    return target_org_id


# ── Token helpers ─────────────────────────────────────────────────────────────

def _build_token_response(
    user: dict[str, Any], refresh_token: str, db: Session | None = None,
    *, session_id: str,
) -> TokenResponse:
    access_token = create_access_token({**create_access_payload(user, db), "sid": session_id})
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user_id=user["id"],
        username=user.get("username"), role=user["role"], name=user["full_name"],
        email=user["email"], category_scope=user.get("category_scope"), org_id=user["org_id"],
        is_platform_admin=bool(user.get("is_platform_admin")), permissions=user["permissions"],
        theme_preference=user.get("theme_preference") or "system",
    )


def issue_login_response(
    db: Session, user, response: Response, request: Request | None = None,
    *, org_id: int | None = None,
) -> TokenResponse:
    """Issue a new revocable session without mutating the user's home tenant."""
    from app.services.authorization_service import denied, resolve_authority
    if not user.is_active or user.status != "active":
        raise denied()
    authority = resolve_authority(db, user, org_id if org_id is not None else user.org_id)
    session_id = f"sess-{uuid.uuid4().hex}"
    refresh_token = create_refresh_token({**create_refresh_payload(authority), "sid": session_id})
    expiry = (datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    auth_session = AuthRepository(db).create_session(
        user_id=user.id, org_id=authority["org_id"], refresh_token=refresh_token,
        expires_at=expiry, session_id=session_id,
    )
    if request:
        auth_session.user_agent = _client_user_agent(request)
        auth_session.ip_address = _client_ip(request)
    UserRepository(db).update_last_login(user.id, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"))
    token_response = _build_token_response(authority, refresh_token, db=db, session_id=session_id)
    _set_auth_cookies(response, token_response.access_token, refresh_token,
                      generate_csrf_token(), account_user_id=user.id)
    return token_response


auth_router = APIRouter(prefix="/auth", tags=["Authentication"], dependencies=[Depends(validate_auth_cookie_mutation)])


@auth_router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(db_session),
) -> TokenResponse:
    client_ip = _client_ip(request)
    ip_key = _rate_key("auth-login-ip", client_ip)
    identifier_key = _rate_key("auth-login-identifier", form_data.username)

    for key in (ip_key, identifier_key):
        retry_after = is_limited(key, limit=LOGIN_FAILURE_LIMIT, window_seconds=LOGIN_FAILURE_WINDOW_SECONDS)
        if retry_after is not None:
            _raise_rate_limit(retry_after)

    try:
        user = authenticate_user(db, form_data.username, form_data.password)
    except HTTPException:
        record_attempt(ip_key, window_seconds=LOGIN_FAILURE_WINDOW_SECONDS)
        record_attempt(identifier_key, window_seconds=LOGIN_FAILURE_WINDOW_SECONDS)
        raise

    clear_attempts(ip_key)
    clear_attempts(identifier_key)
    return issue_login_response(db, user, response, request)


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    body: RefreshRequest | None = None,
    cookie_refresh: str | None = Cookie(default=None, alias="telite_refresh_token"),
    db: Session = Depends(db_session),
) -> TokenResponse:
    refresh_token = cookie_refresh or (body.refresh_token if body else None)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")

    payload = decode_token(refresh_token, token_type="refresh")
    from app.services.authorization_service import authenticate_payload, denied, load_identity
    authority, session = authenticate_payload(db, payload)
    if session.refresh_token != refresh_token:
        raise denied()
    # Serialize rotation; only one concurrent refresh may consume this session.
    from app.models.session import AuthSession
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    changed = db.execute(update(AuthSession).where(
        AuthSession.id == session.id, AuthSession.revoked_at.is_(None)
    ).values(revoked_at=now)).rowcount
    if changed != 1:
        raise denied()
    user = load_identity(db, authority["id"])
    return issue_login_response(db, user, response, org_id=authority["org_id"])


@auth_router.post("/logout")
def logout(
    response: Response,
    body: LogoutRequest | None = None,
    current_user: TokenData = Depends(get_current_user),
    cookie_refresh: str | None = Cookie(default=None, alias="telite_refresh_token"),
    db: Session = Depends(db_session),
) -> dict[str, str]:
    from app.models.session import AuthSession
    db.execute(update(AuthSession).where(
        AuthSession.id == current_user.session_id, AuthSession.user_id == current_user.id,
        AuthSession.org_id == current_user.org_id,
    ).values(revoked_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")))

    _clear_auth_cookies(response)
    return {"status": "logged_out", "user_id": current_user.id}


@auth_router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest, 
    request: Request,
    db: Session = Depends(db_session),
) -> dict[str, str]:
    client_ip = _client_ip(request)
    ip_key = _rate_key("auth-forgot-password-ip", client_ip)
    email_key = _rate_key("auth-forgot-password-email", body.email)

    for key in (ip_key, email_key):
        retry_after = is_limited(key, limit=FORGOT_PASSWORD_LIMIT, window_seconds=FORGOT_PASSWORD_WINDOW_SECONDS)
        if retry_after is not None:
            _raise_rate_limit(retry_after)

    record_attempt(ip_key, window_seconds=FORGOT_PASSWORD_WINDOW_SECONDS)
    record_attempt(email_key, window_seconds=FORGOT_PASSWORD_WINDOW_SECONDS)

    from app.repositories.auth_repo import AuthRepository
    from app.repositories.user_repo import UserRepository
    try:
        set_platform_context(db)
        user_repo = UserRepository(db)
        user = user_repo.get_by_email(body.email)
        
        if user and user.is_active:
            auth_repo = AuthRepository(db)
            reset_record = auth_repo.create_password_reset_token(user.id)
            send_password_reset_email(
                to_email=user.email,
                name=user.full_name,
                token=reset_record.token,
                expires_at=reset_record.expires_at,
            )
    finally:
        clear_rls_context(db)

    # Always return the same message to prevent email enumeration
    return {
        "status": "ok",
        "message": "If an account exists for that email, a password reset link has been sent.",
    }


@auth_router.post("/reset-password")
def reset_password(
    body: ResetPasswordRequest, 
    request: Request,
    db: Session = Depends(db_session),
) -> dict[str, str]:
    client_ip = _client_ip(request)
    ip_key = _rate_key("auth-reset-password-ip", client_ip)

    retry_after = is_limited(ip_key, limit=RESET_PASSWORD_LIMIT, window_seconds=RESET_PASSWORD_WINDOW_SECONDS)
    if retry_after is not None:
        _raise_rate_limit(retry_after)

    record_attempt(ip_key, window_seconds=RESET_PASSWORD_WINDOW_SECONDS)

    import datetime

    from app.repositories.auth_repo import AuthRepository
    from app.repositories.user_repo import UserRepository
    
    try:
        set_platform_context(db)
        auth_repo = AuthRepository(db)
        token_record = auth_repo.get_password_reset_token(body.token)
        
        if not token_record or token_record.used_at is not None:
            raise ValueError("Invalid or expired reset token.")
            
        now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
        if token_record.expires_at < now:
            raise ValueError("Reset token has expired.")
            
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise ValueError("Invalid user state.")
            
        auth_repo.mark_password_reset_token_used(token_record.id)
        user_repo.update_password(user, body.password)
        auth_repo.revoke_all_for_user(user.id)
        user_id = user.id
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        clear_rls_context(db)

    clear_attempts(ip_key)
    return {"status": "password_updated", "user_id": user_id}


@auth_router.get("/me")
def get_me(current_user: TokenData = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "name": current_user.full_name,
        "role": current_user.role,
        "category_scope": current_user.category_scope,
        "org_id": current_user.org_id,
        "is_platform_admin": current_user.is_platform_admin,
        "is_active": True,
        "permissions": current_user.permissions,
        "theme_preference": current_user.theme_preference,
    }


@auth_router.patch("/preferences/theme")
def update_theme_preference(
    body: ThemePreferenceRequest,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(db_session),
) -> dict[str, str]:
    theme_preference = body.theme_preference.strip().lower()
    if theme_preference not in THEME_PREFERENCES:
        raise HTTPException(
            status_code=400,
            detail="theme_preference must be one of: light, dark, system",
        )

    UserRepository(db).update_theme_preference(current_user.id, theme_preference)
    db.commit()
    return {
        "user_id": current_user.id,
        "theme_preference": theme_preference,
    }
