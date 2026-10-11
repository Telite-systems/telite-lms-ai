# Corporate SaaS baseline — Stage 0

Reviewed 11 October 2026 against `main` at `f5afafe6623314cd6fbb397262dbb4ee7419d19a`.
The supplied corporate SaaS plan reviewed the same commit; there is no main-branch drift.

**Acceptance status: BLOCKED.** The baseline and containment proposal are reviewable,
but PostgreSQL isolation/migration evidence, full recovery evidence, authoritative
secret scans and operator credential remediation remain outstanding. Do not advance
to production or claim the chatbot is safe on this evidence.

## Scope and contracts

Preserve React/Vite, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis and Celery.
Preserve company and college behavior. PostgreSQL schema authority remains Alembic
(`docs/adr/004-schema-authority.md`); this PR changes no schema or runtime API.
No tracked `AGENTS.md` or contributor instruction file was found. Read the production
contract and existing security, backup and recovery runbooks before implementation.

At baseline, 539 paths are tracked. Runtime OpenAPI generation in development exposes
198 paths / 232 operations; 70 ORM tables are registered. See `inventory.md` for the
complete routes, table classification and migration graph. OpenAPI generation warns
about a duplicate `create_learning_path_authoring_learning_paths_post` operation ID.
A generated schema demonstrates import/registration only, not endpoint correctness.

## Native LMS and Moodle boundary

The README and Compose stack still describe/run Moodle. However,
`app/models/user.py` marks `moodle_id` deprecated for Phase 6 retirement, and
`app/api/routes/authoring.py` explicitly says Moodle create/update sync is retired.
`app/integrations/` contains only its package initializer. Native authoring, publishing,
snapshots, enrollment, player, quiz, assignments, gradebook, completion and learning
paths are registered in `app/main.py`. Treat Moodle as an unresolved integration
contract; do not remove its service or promise live sync until an operator verifies
which deployment still uses it. `MOODLE_MODE=mock` is configured in CI/Compose;
that setting is not evidence of a working live Moodle integration.

## Existing workflows and evidence

Backend paths below are relative to `telite-backend/`.

| Workflow | Evidence | Verification level |
|---|---|---|
| Tenant/admin provisioning and invitations | `app/api/routes/platform.py`, `tests/test_platform_invitations.py` | Selected synthetic SQLite service/API tests pass; real email delivery not tested |
| Course creation | `app/api/routes/authoring.py`, `tests/test_course_creation.py` | SQLite smoke passed |
| Manual enrollment | `app/repositories/enrollment_repo.py`, `tests/test_manual_enrollment_service.py` | Selected SQLite tests pass; entitlement revocation remains a blocker |
| Learning paths | `app/api/routes/learning_paths.py`, `tests/test_learning_path_runtime.py` | Selected SQLite runtime tests pass; analytics endpoint returns fixed simulated values |
| Tasks | `app/api/routes/tasks.py`, `tests/test_task_workflow.py` | SQLite smoke passed |
| Assignment submission/grading | `app/services/assignment_service.py`, `tests/test_assignment_enrollment_security.py` | Cross-tenant and category grading checks pass on SQLite; enrollment removal assertion fails |
| Quiz/grade-aware completion | `app/services/completion_policy_service.py`, `tests/test_gradebook_g02_integration.py`, `tests/test_gradebook_g03_aggregation.py`, `tests/test_completion_g04_policy.py` | Selected SQLite tests pass; human approval unsupported |
| Publication and snapshots | `app/repositories/publishing_repo.py`, `app/services/snapshot_resolver.py` | Static inspection; restore returns mock success; live-draft fallback exists |
| Company knowledge chatbot | No dedicated chat/knowledge/RAG module in tracked application files | Not implemented; proposed future scope |
| Redis/Celery jobs, storage and production DB | `docker-compose.yml`, `app/workers/`, `app/db/rls.py` | No running services verified in this environment |

See `validation.md` for commands, failures, skips and environment limits. Tests were
run against newly created disposable SQLite files with synthetic configuration only.
No production server, customer database, customer content provider or SMTP was used.

## Authorization baseline

`app/api/auth.py:get_current_user` establishes RLS context from JWT claims, fetches
User and checks `is_active`, but returns JWT role, permissions and platform privilege.
It does not resolve active Membership, tenant status, User.status or current access
session in that function. Suspension/revocation semantics must be reconciled with
legacy role/org fields and refresh/session routes in Stage 1.

`app/core/permissions.py:resolve_permissions` removes disabled tenant capabilities,
but `app/core/rbac.py:has_permission` restores absent permissions through role defaults.
A synthetic reproduction removed `learner.view_courses` from the claims and observed
`has_permission(...) == True`. `check_capability` also treats super_admin specially;
these entry points require one explicit-denial policy.

`validate_csrf` is defined in auth.py, but no use as a route/global dependency was
found by searching application references. It also skips validation when its CSRF
cookie is absent. Review authenticated cookie mutations and actual middleware
behavior before asserting CSRF protection.

The central RLS table list differs from the ORM inventory for seven org_id tables.
This is a coverage-review finding, **not proof that those tables lack DB policies**:
assignment/task policies also exist in individual migrations. Inspect actual
`pg_class`, `pg_policies`, runtime grants, owner/bypass privileges and transaction
reuse under the non-owner application role. Merely setting context or passing SQLite
tests proves no PostgreSQL isolation.

## Sensitive artifacts and containment

Privately inspected both tracked `backups/telite_backup_*.zip` files, including nested
tar archives in memory without extracting or printing their contents. Each contains
one `.env`, one database dump and two nested archives, with 16 non-empty assignments
in secret/token/password/access-key setting categories. One archive contains two
private-key markers and email-like strings. Marker/string counts do not prove key
validity or identify individual data subjects. No credential was tested remotely.

Proposed containment removes the two archives from the feature branch Git index,
adds archive/backup ignore patterns, and adds a tracked-path CI gate. The gate checks
force-added files too, without reading contents. Gitleaks is changed from changed-
commit scanning to all fetched history, with historical suppression fingerprints
removed. Compressed archive inspection and credential rotation still need separate
operator processes; Gitleaks alone does not prove archive safety.

Main has one commit; a full clone has 22 commits reachable across fetched branches.
A limited local scan examined 568 reachable blobs for literal private-key headers,
GitHub token formats and AWS access-key formats: no matches. It did **not** unpack
archives as part of history scanning and is not a substitute for Gitleaks/TruffleHog.
The historical commits named in `docs/security-remediation.md` are not present in
this clone, so their original findings and remediation cannot be independently
verified here. Archive inspection separately found the private-key markers above.

Deletion from a new tree does not remove earlier blobs, public/forked copies, or
exposed credentials. The operator must classify and rotate affected credentials,
review data exposure, preserve required recovery backups in encrypted restricted
storage, and coordinate any history remediation. No history rewrite, rotation,
production deployment or external credential verification was performed.

## Release and rollback

Changed files are documentation, the source gate/tests, ignore rules, security CI,
and removal of the two tracked archives. No migrations, API or application behavior
change. Reverting source-gate/CI changes restores prior behavior but reopens the
artifact leak path; never recommit the archives to roll back. Runtime image/database
rollback is unnecessary for this PR. Gate failures emit paths only and exit nonzero;
missing Git/index access is an error, not a pass.

Operational evidence to retain: source-artifact check outcome, redacted scanner
status, dependency audit results, CI/JUnit counts and skips, non-owner RLS matrix,
backup age, successful restore timestamp and measured RPO/RTO. Configure required
branch checks before treating green CI as an enforced gate. GitHub's main branch
response reported `protected=false` at review time.

Next bounded task: reconcile enrollment access/revocation policy and reproduce its
failing assertion on disposable PostgreSQL, then complete Stage 1 membership and
capability hardening with compatibility tests. Do not silently alter free-course or
legacy category access rules to make the failing test pass.
