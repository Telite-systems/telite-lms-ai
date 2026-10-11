"""Current authority, revocable sessions and cookie-auth mutation regressions."""
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Response

from app.api.auth import TokenData, issue_login_response
from app.core.permissions import check_capability, require_capability, resolve_permissions
from app.core.rbac import Permission, has_permission, require_permission
from app.core.security import create_access_token, decode_token
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role_permission import RolePermission
from app.models.session import AuthSession
from app.repositories.user_repo import UserRepository

ORG = 9901


def seed(db, *, platform=False, kind="company"):
    db.add(Organization(id=ORG, name="Synthetic Corp", type=kind, domain="synthetic.invalid",
                        slug="synthetic-corp", status="active"))
    db.flush()
    return UserRepository(db).create_user(
        email="employee@example.invalid", username="synthetic", full_name="Synthetic Employee",
        role="platform_admin" if platform else "super_admin", org_id=ORG,
        password="Synthetic-password-123!", is_platform_admin=platform,
    )


def issue(db, user):
    result = issue_login_response(db, user, Response())
    db.commit()
    return result


def headers(result):
    return {"Authorization": f"Bearer {result.access_token}"}


@pytest.mark.parametrize("kind", ["company", "college"])
def test_current_membership_overrides_stale_role(client, db_session, kind):
    user = seed(db_session, kind=kind)
    result = issue(db_session, user)
    assert client.get("/auth/me", headers=headers(result)).json()["role"] == "super_admin"
    membership = db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one()
    membership.role = "learner"
    db_session.commit()
    response = client.get("/auth/me", headers=headers(result))
    assert response.status_code == 200
    assert response.json()["role"] == "learner"
    assert Permission.ORG_MANAGE_USERS not in response.json()["permissions"]
    assert user.role == "super_admin"


@pytest.mark.parametrize("state", ["user_active", "user_status", "membership", "missing_membership", "tenant", "session", "expiry"])
def test_existing_access_and_refresh_deny_after_revocation(client, db_session, state):
    user = seed(db_session)
    result = issue(db_session, user)
    if state == "user_active":
        user.is_active = False
    elif state == "user_status":
        user.status = "suspended"
    elif state in {"membership", "missing_membership"}:
        member = db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one()
        if state == "membership":
            member.status = "suspended"
        else:
            db_session.delete(member)
    elif state == "tenant":
        db_session.get(Organization, ORG).status = "suspended"
    else:
        session = db_session.get(AuthSession, decode_token(result.access_token)["sid"])
        if state == "session":
            session.revoked_at = "2026-01-01 00:00:00"
        else:
            session.expires_at = (datetime.now(UTC) - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    db_session.commit()
    assert client.get("/auth/me", headers=headers(result)).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": result.refresh_token}).status_code == 401


def test_revoked_platform_flag_wins_over_old_jwt(client, db_session):
    user = seed(db_session, platform=True)
    result = issue(db_session, user)
    user.is_platform_admin = False
    UserRepository(db_session).upsert_membership(user_id=user.id, org_id=ORG, role="learner")
    db_session.commit()
    response = client.get("/auth/me", headers=headers(result))
    assert response.status_code == 200
    assert response.json()["is_platform_admin"] is False
    assert response.json()["role"] == "learner"


def test_all_permission_guards_honor_current_disable(client, db_session):
    user = seed(db_session)
    result = issue(db_session, user)
    key = Permission.MEDIA_UPLOAD
    # Duplicates may exist in legacy override data: deny wins in either order.
    for enabled in (False, True):
        db_session.add(RolePermission(org_id=ORG, role="super_admin", permission_key=key, enabled=enabled))
    db_session.commit()
    response = client.get("/auth/me", headers=headers(result))
    assert key not in response.json()["permissions"]
    actor = TokenData(id=user.id, email=user.email, full_name=user.full_name, org_id=ORG,
                      role="super_admin", permissions=response.json()["permissions"])
    assert not has_permission(actor, key)
    assert not actor.has_permission(key)
    calls = [lambda: require_permission(key)(current_user=actor),
             lambda: require_capability(key)(db=db_session, current_user=actor),
             lambda: check_capability(db_session, actor, key)]
    for call in calls:
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 403
    assert key not in resolve_permissions("super_admin", org_id=ORG, db=db_session)


def test_explicit_empty_list_denies_role_defaults():
    actor = TokenData(id="synthetic", email="synthetic@example.invalid", full_name="Synthetic",
                      role="super_admin", org_id=ORG, permissions=[])
    assert not has_permission(actor, Permission.MEDIA_UPLOAD)
    assert not actor.has_permission(Permission.MEDIA_UPLOAD)


def test_sessionless_wrong_subject_and_wrong_tenant_tokens_deny(client, db_session):
    user = seed(db_session)
    result = issue(db_session, user)
    sid = decode_token(result.access_token)["sid"]
    for payload in ({"sub": user.id, "org_id": ORG},
                    {"sub": user.id, "org_id": ORG, "sid": "unknown"},
                    {"sub": "another-user", "org_id": ORG, "sid": sid},
                    {"sub": user.id, "org_id": ORG+1, "sid": sid},
                    {"org_id": ORG, "sid": sid}):
        token = create_access_token(payload)
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_org_switch_checks_membership_without_mutating_home(client, db_session):
    user = seed(db_session)
    db_session.add(Organization(id=ORG+1, name="Synthetic Second", type="company", domain="second.invalid", status="active"))
    db_session.flush()
    db_session.add(Membership(user_id=user.id, org_id=ORG+1, role="reviewer", status="active"))
    result = issue(db_session, user)
    assert client.post("/auth/sessions/switch-org", json={"target_org_id": ORG+2}, headers=headers(result)).status_code == 401
    response = client.post("/auth/sessions/switch-org", json={"target_org_id": ORG+1}, headers=headers(result))
    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"
    db_session.refresh(user)
    assert user.org_id == ORG
    assert user.role == "super_admin"
    assert client.get("/auth/me").json()["org_id"] == ORG+1


def test_cookie_mutations_require_pair_and_bearer_only_passes(client, db_session):
    result = issue(db_session, seed(db_session))
    client.cookies.set("telite_access_token", result.access_token)
    assert client.patch("/auth/preferences/theme", json={"theme_preference": "dark"}).status_code == 403
    client.cookies.set("telite_csrf_token", "synthetic-pair")
    assert client.patch("/auth/preferences/theme", json={"theme_preference": "dark"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.patch("/auth/preferences/theme", json={"theme_preference": "dark"}, headers={"X-CSRF-Token": "synthetic-pair"}).status_code == 200
    client.cookies.clear()
    assert client.patch("/auth/preferences/theme", json={"theme_preference": "light"}, headers=headers(result)).status_code == 200


def test_cookie_refresh_cannot_use_bearer_to_skip_csrf(client, db_session):
    result = issue(db_session, seed(db_session))
    client.cookies.set("telite_refresh_token", result.refresh_token)
    assert client.post("/auth/refresh", headers=headers(result)).status_code == 403
    client.cookies.set("telite_csrf_token", "synthetic-pair")
    response = client.post("/auth/refresh", headers={**headers(result), "X-CSRF-Token": "synthetic-pair"})
    assert response.status_code == 200
    assert client.get("/auth/me", headers=headers(result)).status_code == 401


def test_refresh_rotation_and_logout_revoke_sessions(client, db_session):
    result = issue(db_session, seed(db_session))
    response = client.post("/auth/refresh", json={"refresh_token": result.refresh_token})
    assert response.status_code == 200
    rotated = response.json()
    client.cookies.clear()
    assert client.post("/auth/refresh", json={"refresh_token": result.refresh_token}).status_code == 401
    assert client.get("/auth/me", headers=headers(result)).status_code == 401
    current_headers = {"Authorization": f"Bearer {rotated['access_token']}"}
    assert client.post("/auth/logout", headers=current_headers).status_code == 200
    assert client.get("/auth/me", headers=current_headers).status_code == 401


def test_home_role_update_does_not_reactivate_suspended_membership(db_session):
    user = seed(db_session)
    membership = db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one()
    membership.status = "suspended"
    UserRepository(db_session).update_role(user, role="learner")
    assert membership.role == "learner"
    assert membership.status == "suspended"


def test_one_time_membership_backfill_preserves_suspension(db_session, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    user = seed(db_session)
    member = db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one()
    member.status = "suspended"
    db_session.flush()
    path = Path(__file__).parents[1] / "app/db/migrations/versions/corp_s1_authority.py"
    spec = importlib.util.spec_from_file_location("corp_authority_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: db_session.connection()))
    migration.upgrade()
    db_session.expire_all()
    assert db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one().status == "suspended"
    db_session.delete(db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one())
    db_session.flush()
    migration.upgrade()
    assert db_session.query(Membership).filter_by(user_id=user.id, org_id=ORG).one().role == "super_admin"


def test_reserved_corporate_roles_have_no_tenant_administration_grants():
    for role, capability in (("manager", Permission.TEAM_VIEW_READINESS),
                             ("content_owner", Permission.KNOWLEDGE_MANAGE),
                             ("reviewer", Permission.COMPETENCY_REVIEW)):
        permissions = resolve_permissions(role)
        assert capability in permissions
        assert Permission.ORG_MANAGE_USERS not in permissions
        assert Permission.PLATFORM_MANAGE_ORGS not in permissions


def test_session_listing_uses_sid_and_omits_expired_records(client, db_session):
    user = seed(db_session)
    result = issue(db_session, user)
    db_session.add(AuthSession(id="expired-synthetic", user_id=user.id, org_id=ORG,
                              refresh_token="expired-synthetic-token", expires_at="2020-01-01 00:00:00"))
    db_session.commit()
    response = client.get("/auth/sessions/", headers=headers(result))
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["session_id"] == decode_token(result.access_token)["sid"]
    assert response.json()[0]["is_current"] is True
    assert "telite_auth_denials_total" in client.get("/metrics").text


def test_demoted_membership_cannot_use_legacy_user_role_for_draft_access(db_session):
    from app.models.course import Course
    from app.repositories.enrollment_repo import EnrollmentRepository
    user = seed(db_session)
    course = Course(id="synthetic-private-course", name="Synthetic Draft", org_id=ORG,
                    slug="synthetic-draft", category_slug="synthetic", status="draft")
    db_session.add(course)
    db_session.flush()
    actor = TokenData(id=user.id, email=user.email, full_name=user.full_name, org_id=ORG,
                      role="learner", permissions=resolve_permissions("learner"))
    assert user.role == "super_admin"
    assert not EnrollmentRepository(db_session).has_access(user.id, course.id, ORG, actor=actor)
