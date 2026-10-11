"""Connection checks fail closed without requiring a live database."""
import pytest
from sqlalchemy.engine import make_url

from app.db.engine import _build_dsn, _verify_runtime_role


class Connection:
    def __init__(self, flags, owned):
        self.answers = iter([flags, (owned,)])
        self.closed = False
        self.rolled_back = False

    def cursor(self):
        return self

    def execute(self, _query):
        pass

    def fetchone(self):
        return next(self.answers)

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


@pytest.mark.parametrize("flags,owned", [((True, False, False), 0), ((False, True, False), 0), ((False, False, True), 0), ((False, False, False), 1), (None, 0)])
def test_runtime_role_rejects_privileged_or_owned_connections(flags, owned):
    conn = Connection(flags, owned)
    with pytest.raises(RuntimeError):
        _verify_runtime_role(conn, None)
    assert conn.closed and conn.rolled_back


def test_runtime_role_accepts_non_owner_without_bypass():
    conn = Connection((False, False, False), 0)
    _verify_runtime_role(conn, None)
    assert conn.closed and conn.rolled_back


def test_runtime_credentials_are_used_in_fallback_dsn(monkeypatch):
    settings = {
        "TELITE_DATABASE_URL": "", "TELITE_DB_BACKEND": "postgres",
        "TELITE_POSTGRES_HOST": "synthetic.invalid", "TELITE_POSTGRES_DB": "synthetic",
        "TELITE_POSTGRES_USER": "migration", "TELITE_POSTGRES_PASSWORD": "synthetic-migration-password",
        "TELITE_RUNTIME_POSTGRES_USER": "runtime", "TELITE_RUNTIME_POSTGRES_PASSWORD": "synthetic-runtime-password",
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    url = make_url(_build_dsn())
    assert url.username == "runtime"
    assert url.password == "synthetic-runtime-password"
