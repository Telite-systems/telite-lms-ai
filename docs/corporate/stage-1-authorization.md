# Stage 1 — current authority and tenant isolation

Implementation proposal on `corporate/stage-1-authorization`, stacked on Stage 0
commit `c022929423cba406b4f284bb5817b1102d626a5f` / PR #21. No deployment or merge.
The user explicitly requested continued implementation while Stage 0 release
blockers remain open. This document describes actual changes, not launch approval.

## Behavior and compatibility

Every authenticated request resolves the current active User, active Organization,
and active Membership. JWT role, category, permission and platform-privilege claims
are not authority. The current persisted platform flag retains the existing platform
bypass contract; tenant membership cannot grant platform privilege. A narrow signed-
subject identity lookup uses temporary bypass before immediately clearing it. This
is privileged authentication code, not a barrier against arbitrary SQL execution.

`resolve_permissions` resolves defaults and tenant overrides; explicit denial wins,
including duplicate legacy overrides. All three capability guard entry points and
TokenData.has_permission now agree. An explicit empty list denies role defaults.
Internal legacy TokenData instances with omitted permissions may use static defaults;
HTTP actors always receive a fresh resolved list. Role-only endpoint guards still
need operation-by-operation capability adoption where their contract is role-based.

Access and refresh tokens bind to `AuthSession.id` via `sid`. Each request checks
subject, tenant, revocation and expiry. Existing sessionless access/refresh tokens
are rejected: users must sign in again after rollout. No global JWT-secret rotation
is required for this format change, but Stage 0 exposure remediation still requires
operator credential review/rotation. Refresh consumes the old session with an atomic
conditional update, then issues a new session; concurrent consumption can succeed
only once. Logout revokes the current sid even without a refresh cookie. Session
listing uses sid and excludes expired records.

Cookie-authenticated mutations require the CSRF cookie/header pair. Bearer-only API
calls use header authentication. Cookie refresh/browser-account switch cannot skip
CSRF by adding an irrelevant bearer header. Current frontend already sends the pair.
Account switching validates current membership/session state without mutating the
persisted User.org_id, role or category. User identity remains tenant-scoped; this
change does not claim all LMS services support cross-org global identities yet.

Existing home-role editors update the home Membership without reactivating suspended
memberships. New UserRepository-created tenant users receive a home membership.
The one-time Alembic backfill creates missing legacy home memberships from User
role/category/activity state, leaving existing memberships untouched. Operators
must review historical hard-deleted memberships before applying this backfill:
absence cannot distinguish a legacy missing row from a prior deliberate deletion.
There is no runtime fallback that restores deleted memberships.

Assignment submission/read/download and native quiz submission require an explicit
approved enrollment or the existing matching category/staff grant. Free/same-tenant
course browsing no longer implicitly grants assignment/quiz submission rights.
Enrollment checks receive the current resolved actor, so a legacy User.role cannot
restore demoted membership privileges for drafts or assessments.
Category-wide grants remain a separate legacy entitlement; removing one enrollment
does not revoke an independently valid category grant. Course-level entitlement
normalization remains future work. Existing EnrollmentRequest is category-based,
so this change does not invent course-specific grants.

Reserved manager/team-readiness, reviewer/competency and content-owner/knowledge
capabilities grant no tenant administration. Their future endpoints must enforce
team, assigned-reviewer and document scopes. There are no new team/readiness/knowledge
endpoints in this PR; team isolation acceptance depends on Stages 2/4/5.

## PostgreSQL and role changes

Alembic revision `corp_s1_authority` follows `i1j2k3l4m5n6`. It performs the membership
backfill and adds a restrictive tenant guard to every actual public table with org_id,
plus organization_branding.organization_id. ENABLE/FORCE RLS apply to those tables.
Existing actor-specific permissive policies remain; a default permissive tenant
policy is created only where none exists. Restrictive policies cannot broaden
assignment ownership/reviewer policies. The helper table list and branding column
mapping are reconciled. These SQL changes are exercised on migrated PostgreSQL in the dedicated CI job.

RLS context is stored per SQLAlchemy Session and reapplied with SET LOCAL when a
transaction begins, including after commit/retry. Actor ID/role also survive those
transitions. Fresh Sessions on reused connections default to no tenant/no bypass/no
actor. Clear resets all four values. Worker tenant/platform session helpers use the
same context path; actual Redis/Celery deliveries and full worker workflows have
not been exercised locally.

Fallback DSN building now uses configured runtime credentials. An explicit
TELITE_DATABASE_URL still takes precedence; operators must set it to the runtime
role, not the migrator. Production application pool connections reject superuser,
BYPASSRLS and ownership of tenant tables. Migration runner explicitly identifies
its connection purpose and uses TELITE_MIGRATION_DATABASE_URL. Container entrypoint
replaces fallback owner credentials and removes migration/root env credentials from
API/worker children when runtime credentials are configured. Ensure any explicit
DSN is a runtime DSN and provision a distinct role before release. Never set the
migration connection-purpose flag in application deployments.

Legacy databases without Alembic history now fail with reconciliation instructions
instead of silently stamping head and skipping the new data/policy migration.
Migration connection diagnostics no longer print a raw DSN prefix.

## Certificate resource egress correction

Automatic approval review rejected an initial regression run because PDF generation
requested an external QR service with a verification URL/token. That action was not
retried. QR images are now generated locally with qrcode and embedded in the PDF.
The renderer fetcher accepts only bounded embedded image data and rejects network
and local-file URLs. Remote logo/signature URLs therefore no longer load; prepare
approved image data internally before rendering. Tests assert no external QR URL
and verify rejection of external/private-network/file resources. This is a safer
implementation change, not permission to send tokens externally.

## Validation and evidence

Locally executed on Python 3.12.14 with the isolated dependency environment and
fresh disposable SQLite databases; no customer data or production credentials used.

- Initial authority/media suite: 22 passed.
- Follow-up authority, certificate, assignment and published-version/quiz suite:
  50 passed, 1 PostgreSQL-specific actor-context test deselected, 11 warnings.
- Combined compatibility suite: JUnit records 115 tests, zero failures/errors/skips.
  PostgreSQL actor-context test was explicitly deselected. This is SQLite evidence.
- Follow-up authority/runtime-role/health run: 32 passed, 4 new live PostgreSQL tests skipped.
- Latest role/assessment/assignment compatibility follow-up: 51 passed, 1 PostgreSQL-specific test deselected.
- New runtime-role tests use controlled fake DBAPI responses, not PostgreSQL proof.
- Relevant modified/new backend modules pass Ruff; shell entrypoint parses; workflows
  parse as YAML; source-artifact gate and diff whitespace checks remain required.

Tests were updated to issue real server sessions/memberships instead of sessionless
JWT fixtures. Contract FakeDb now models Session.info/bind. Older Phase C fixtures
had an undefined `false`, missing CourseVersion ID, and a stale flat response shape;
fixtures now use valid IDs/Python booleans and inspect published sections/modules.
The frozen-version and answer-key stripping assertions are retained. Authorization
failures exposed by those assertions were fixed, not disabled.

The dedicated `corporate-authorization.yml` workflow uses a disposable PostgreSQL 16
database, applies actual Alembic migrations, provisions a separate non-owner role,
and enables `tests/test_authorization_postgres.py`. It checks actual ENABLE/FORCE and
restrictive guard coverage, role ownership/bypass flags, A/B reads/writes, missing
context, commit/rollback and single-connection pool reuse, HTTP current authority,
and concurrent refresh consumption. A real notification-worker test uses an in-memory
delivery stub and forged cross-tenant user reference; no messages are sent. It then
downgrades/re-upgrades this revision.
The main critical regression workflow also runs authority, runtime-role, certificate
resource and assignment-revocation tests. CI results must be read before declaring
PostgreSQL isolation verified; local live tests are intentionally skipped.

Remote Stage 1 evidence: commit `2bbafb54bc56f8c34e38fb9790572c6faeeedcbf`,
[run 38160082795](https://github.com/Telite-systems/telite-lms-ai/actions/runs/38160082795),
passed 42 regression tests, four live non-owner PostgreSQL tests, actual migration
and runtime-role provisioning, and downgrade/re-upgrade. Commit
`747b3c8b66724de52fa36e644d44be5a091418f3` strengthens the suspension assertion to
use the newly refreshed live token; its dedicated job also passed. The added worker
check requires the next CI run before claiming worker isolation verified. These
checks do not constitute a complete endpoint/worker/platform-bypass audit.

Stage 0 remote results: backend smoke/critical regression, PostgreSQL migration chain,
frontend and Docker build passed; secret and source-artifact jobs passed. Dependency
review and Python dependency/image/filesystem scans failed. Those findings and
credential rotation/full restore remain release blockers; scanner success is not
proof that compressed historical archives or exposed credentials are safe.

## Failure behavior, observability and rollback

Missing/inactive user, tenant, membership, session, malformed subject/sid and expired
session return a consistent non-disclosing 401. Capability/CSRF denials return 403.
Database failures fail requests; no token-claim fallback grants access. Monitor the
new `telite_auth_denials_total` counter with existing request/5xx counts and request-ID
logs, permission.denied audits, DB role startup failures and refresh rates. Counters
are per-process and require aggregation; this is not a complete observability stack.

Rollout order: review/back up identity state privately; remediate Stage 0 exposure;
provision distinct migration/runtime roles; apply migration on staging; pass non-owner
CI and real worker/browser tests; announce re-login requirement; promote only after
all acceptance gates. No permissive feature-disable switch is added for auth.

Rollback uses the previous application image only after checking compatibility on
staging. The additive membership rows are retained. Migration downgrade removes the
new named corporate policies but intentionally retains enabled/FORCE RLS and
membership data; it does not erase grants/evidence or reopen owner bypass. Tables
whose only permissive policy was new can fail closed after downgrade until a verified
policy is restored or the revision is re-upgraded. Do not restore unsafe token fallback,
external QR requests, sensitive archives or disable security tests as recovery.

**Acceptance remains pending** until the new PostgreSQL CI is green, full route and
worker scope checks are evidenced, and inherited Stage 0 release blockers are resolved.
