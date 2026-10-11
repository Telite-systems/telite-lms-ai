# Stage 0 validation record

Executed 11 October 2026 on baseline `f5afafe6623314cd6fbb397262dbb4ee7419d19a`.
Python 3.12.14, Node 24.19.0, npm 11.9.0. CI requests Python 3.12/Node 20.
No Docker, PostgreSQL binaries, Gitleaks or TruffleHog were available locally.

## Actual checks

| Command | Actual outcome |
|---|---|
| `python -m venv <scratch-venv>`; `pip install -r requirements-dev.txt` | Pass, isolated venv; requirements installed unchanged |
| `pip check` | Pass, no broken requirements |
| CI release-tooling `ruff check` command below | Pass |
| `alembic heads` | One head: `i1j2k3l4m5n6` |
| `npm ci --ignore-scripts` | Pass; install hooks suppressed; this differs from CI's plain npm ci |
| `npm run lint:ci` | Pass under configured threshold; 0 errors, 7 warnings |
| `npm run test:frontend` | 21 passed, 0 failed/skipped |
| `npm run build` | Pass; Vite build generated dist |
| Supplemental backend smoke below | 8 passed, 4 skipped; SQLite only |
| Supplemental backend service/regression below | 33 passed, 2 failed; SQLite only |
| Synthetic absent-permission reproduction | `has_permission` returns True through role fallback; confirms policy gap |
| OpenAPI generation | 198 paths / 232 operations; duplicate learning-path operation ID warning |
| Limited literal history scan | 568 blobs across 22 reachable commits; 3 pattern classes, no matches; compressed content excluded |
| Private archive inspection | Two env-bearing backups; two private-key markers inside one; no contents/values emitted |

### Backend commands

Run in `telite-backend/` with the isolated venv active. Supplemental checks used:

```bash
export ENVIRONMENT=development
export TELITE_AUTH_SECRET=stage0-synthetic-auth-secret-with-more-than-32-characters
export TELITE_PASSWORD_SALT=stage0-synthetic-salt
export TELITE_DATABASE_URL=sqlite:////ABSOLUTE/SCRATCH/stage0-unit.sqlite
export TELITE_TEST_DATABASE_URL="$TELITE_DATABASE_URL"
export TELITE_USE_ALEMBIC=false
export REDIS_ENABLED=false
export MOODLE_MODE=mock
export PYTHONPATH=.
ruff check scripts/validate_production_env.py tests/test_health.py \
  tests/test_api_verification.py tests/test_rls_verification.py tests/test_rls_isolation.py
alembic heads
pytest -q tests/test_health.py tests/test_course_creation.py tests/test_task_workflow.py \
  tests/test_rls_isolation.py tests/test_rls_verification.py --junitxml=../test-results/stage0-smoke.xml
```

For the second run, both DB URLs pointed to a separate fresh `stage0-regression.sqlite`:

```bash
pytest -q tests/test_manual_enrollment_service.py tests/test_platform_invitations.py \
  tests/test_learning_path_runtime.py tests/test_completion_g04_policy.py \
  tests/test_assignment_enrollment_security.py tests/test_gradebook_g02_integration.py \
  tests/test_gradebook_g03_aggregation.py --junitxml=../test-results/stage0-regression.xml
```

JUnit output was retained in scratch during review, not committed. Four smoke tests
skip because `TELITE_RUN_LIVE_RLS_TESTS` is unset; these are missing isolation evidence.
Failures were preserved without changing assertions:

1. `test_assignment_submit_requires_enrollment`: expected HTTPException after deleting
   enrollment; none raised. `EnrollmentRepository.has_access` still permits same-tenant
   learners and free/category access. Reconcile the product entitlement contract and
   reproduce restricted revocation on PostgreSQL before fixing it.
2. `test_assignment_actor_context_sets_rls_claims`: SQLite has no `current_setting`.
   Unsupported test environment; run on PostgreSQL rather than changing the test.

Deprecation warnings include FastAPI/Starlette TestClient, Pydantic class Config and
naive utcnow calls. No production DB or seeded customer archive was used for tests.

## Checks still required

Disposable PostgreSQL fresh migrations, one-step downgrade/re-upgrade, live non-owner
RLS tests (including retries/pooling/workers), complete CI critical regression,
Docker Compose config/images, real Moodle contract, Redis/Celery behavior, browser
journeys, full backup/media restoration, dependency vulnerability scans, Gitleaks,
TruffleHog and Trivy. No current vulnerability clearance is claimed from installation
or old remediation notes. Pin audit policy and verify provider approvals before AI.

`tests/conftest.py` drops/recreates the public schema. Set BOTH database URLs explicitly
to a disposable test database before running tests; never point these commands at a
shared development or production database. Alembic migration evidence is separate
from ORM create_all tests, which do not demonstrate migration-installed RLS policies.

## Source prevention checks

From repository root:

```bash
python -m unittest discover -s .github/scripts -p 'test_source_artifacts.py'
python .github/scripts/check-source-artifacts.py
```

The three source-gate tests pass and include an actual temporary Git index with a
force-added ignored archive and staged removal. Before removal, the gate correctly
fails on the two tracked ZIP paths. After staging their removal, the gate passed. New gate scripts passed Ruff; the security workflow parsed as valid YAML and retained full-history/redacted Gitleaks settings. `git diff --cached --check` passed. A
path gate is intentionally limited and does not replace content/history scanning.
