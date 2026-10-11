"""Disposable migrated PostgreSQL evidence under a real non-owner runtime role.

Run ONLY in a disposable database with TELITE_RUN_AUTH_POSTGRES_TESTS=1.
No inherited conftest engine/client fixture is used: they recreate ORM-only schema.
"""
import os

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.rls import clear_rls_context, set_rls_context
from app.models.membership import Membership
from app.models.user import User

pytestmark = pytest.mark.skipif(
    os.getenv("TELITE_RUN_AUTH_POSTGRES_TESTS") != "1",
    reason="Requires explicitly disposable migrated PostgreSQL and runtime role",
)
A, B = 89901, 89902


@pytest.fixture(scope="module")
def runtime():
    admin = create_engine(os.environ["TELITE_MIGRATION_DATABASE_URL"])
    engine = create_engine(os.environ["TELITE_AUTH_RUNTIME_TEST_URL"], pool_size=1, max_overflow=0)
    with admin.begin() as conn:
        for org, suffix in ((A, "a"), (B, "b")):
            conn.execute(text("""INSERT INTO organizations (id, name, type, domain, slug, status, plan)
                VALUES (:id, :name, 'company', :domain, :slug, 'active', 'test')"""),
                {"id": org, "name": f"Synthetic S1 {suffix}", "domain": f"s1-{suffix}.invalid", "slug": f"s1-{suffix}"})
        # ORM fills model defaults while the admin connection can insert fixtures.
    with Session(admin) as db:
        for org, suffix in ((A, "a"), (B, "b")):
            db.add(User(id=f"synthetic-s1-{suffix}", username=f"s1-{suffix}", email=f"s1-{suffix}@example.invalid",
                        full_name="Synthetic", role="learner", org_id=org, password_hash="synthetic",
                        avatar_initials="SY", gradient_start="#000", gradient_end="#fff"))
        db.flush()
        for org, suffix in ((A, "a"), (B, "b")):
            db.add(Membership(user_id=f"synthetic-s1-{suffix}", org_id=org, role="learner", status="active"))
        db.commit()
    yield engine, admin
    with admin.begin() as conn:
        conn.execute(text("DELETE FROM organizations WHERE id IN (:a, :b)"), {"a": A, "b": B})
    engine.dispose()
    admin.dispose()


def test_runtime_role_and_every_actual_tenant_table_policy(runtime):
    engine, admin = runtime
    with engine.connect() as conn:
        role = conn.execute(text("SELECT rolsuper, rolbypassrls, rolcreaterole FROM pg_roles WHERE rolname=current_user")).one()
        assert tuple(role) == (False, False, False)
        owned = conn.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user")).scalar()
        assert owned == 0
    with admin.connect() as conn:
        inspector = inspect(conn)
        tables = [table for table in inspector.get_table_names(schema="public")
                  if "org_id" in {c["name"] for c in inspector.get_columns(table, schema="public")}
                  or table == "organization_branding"]
        assert "assignment_submissions" in tables
        for table in tables:
            row = conn.execute(text("""SELECT relrowsecurity, relforcerowsecurity FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname=:table"""), {"table": table}).one()
            assert tuple(row) == (True, True), table
            guards = conn.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=:table AND policyname='corporate_tenant_guard' AND permissive='RESTRICTIVE'"), {"table": table}).scalar()
            assert guards == 1, table


def test_non_owner_reads_commit_retry_and_pool_reuse(runtime):
    engine, _ = runtime
    for org, expected in ((A, "synthetic-s1-a"), (B, "synthetic-s1-b")):
        with Session(engine) as db:
            set_rls_context(db, org)
            for transition in (db.commit, db.rollback, db.commit):
                transition()
                assert db.scalars(select(User.id)).all() == [expected]
            clear_rls_context(db)
            db.commit()
            assert db.scalars(select(User.id)).all() == []
    # Reuse the single pooled connection with a fresh Session and no context.
    with Session(engine) as db:
        assert db.scalars(select(User.id)).all() == []


def test_non_owner_cross_tenant_writes_fail_closed(runtime):
    engine, _ = runtime
    with Session(engine) as db:
        set_rls_context(db, A)
        assert db.execute(text("UPDATE users SET full_name='Wrong' WHERE id='synthetic-s1-b'")).rowcount == 0
        db.add(User(id="synthetic-s1-cross", username="s1-cross", email="s1-cross@example.invalid",
                    full_name="Synthetic", role="learner", org_id=B, password_hash="synthetic",
                    avatar_initials="SY", gradient_start="#000", gradient_end="#fff"))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
        assert db.scalars(select(User.id)).all() == ["synthetic-s1-a"]


def test_http_runtime_authority_and_concurrent_refresh(runtime):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import Response
    from fastapi.testclient import TestClient

    from app.api.auth import issue_login_response
    from app.db.engine import db_session
    from app.main import create_app
    from app.services.authorization_service import load_identity
    engine, admin = runtime
    with Session(engine) as db:
        token = issue_login_response(db, load_identity(db, "synthetic-s1-a"), Response())
        db.commit()
    app = create_app()
    def scoped_session():
        with Session(engine) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[db_session] = scoped_session
    headers = {"Authorization": f"Bearer {token.access_token}"}
    client = TestClient(app)
    assert client.get("/auth/me", headers=headers).json()["org_id"] == A
    def refresh(_):
        independent_client = TestClient(app)
        try:
            return independent_client.post("/auth/refresh", json={"refresh_token": token.refresh_token}).status_code
        finally:
            independent_client.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(refresh, range(2))) == [200, 401]
    assert client.get("/auth/me", headers=headers).status_code == 401
    with admin.begin() as conn:
        conn.execute(text("UPDATE memberships SET status='suspended' WHERE user_id='synthetic-s1-a'"))
    assert client.get("/auth/me", headers=headers).status_code == 401
    with admin.begin() as conn:
        conn.execute(text("UPDATE memberships SET status='active' WHERE user_id='synthetic-s1-a'"))
