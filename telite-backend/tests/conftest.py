import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.db.engine import dispose_engine
from app.models.base import Base


TEST_DATABASE_URL = os.getenv(
    "TELITE_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres123@127.0.0.1:55432/test_telite_backend",
).replace("postgresql+psycopg2://", "postgresql+psycopg://", 1).replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)


def _reset_schema(engine) -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        return
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(engine):
    os.environ["TELITE_DATABASE_URL"] = TEST_DATABASE_URL
    dispose_engine()
    with TestClient(create_app()) as test_client:
        yield test_client
    dispose_engine()


@pytest.fixture(scope="session")
def engine():
    # Use manual local postgres instance on port 55432
    os.environ["TELITE_DATABASE_URL"] = TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    
    # Create all tables
    _reset_schema(engine)
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Teardown
    _reset_schema(engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    # Create all tables cleanly for each test
    _reset_schema(engine)
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def authenticated_token(db, user_id, org_id):
    """Synthetic fixture: explicit membership and a real server-issued session."""
    from fastapi import Response
    from app.api.auth import issue_login_response
    from app.models.membership import Membership
    from app.models.user import User
    user = db.get(User, user_id)
    if not db.query(Membership).filter_by(user_id=user_id, org_id=org_id).first():
        db.add(Membership(user_id=user_id, org_id=org_id, role=user.role,
                          category_scope=user.category_scope, status="active"))
        db.flush()
    token = issue_login_response(db, user, Response(), org_id=org_id).access_token
    db.commit()
    return token
