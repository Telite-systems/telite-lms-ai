# Corporate SaaS gap backlog

Baseline: `f5afafe6623314cd6fbb397262dbb4ee7419d19a`, 11 October 2026.
Backend evidence paths are relative to `telite-backend/`. Stages are sequential;
rows describe required work, not completed features.

| ID / priority | Stage / owner | Evidence and concrete task | Acceptance |
|---|---|---|---|
| SEC-01 / P0 | 0 / operator | Tracked ZIPs contain env/dumps and private-key markers. Proposed removal and prevention are in this PR. | Classify/rotate all possibly exposed credentials; private recovery copy; coordinated history remediation; redacted full scanner evidence. Deletion alone never closes this item. |
| AUTH-01 / P0 | 1 / backend | `api/auth.py:get_current_user` uses JWT authority. Resolve active User, tenant, Membership and session from server state. | Old JWT denies after privilege/membership/session/tenant suspension; valid legacy and college logins preserved. |
| AUTH-02 / P0 | 1 / backend | `core/rbac.py` role fallback reverses capability denial; `core/permissions.py` has additional semantics. Consolidate authority. | Tenant explicit disable wins across every guard, including super-admin policy; no permissive fallback. |
| AUTH-03 / P0 | 1 / backend | CSRF validator has no found dependency references and skips absent cookie. Enforce on cookie mutations. | Cookie-auth missing/wrong CSRF denies; valid pair passes; documented bearer behavior; coverage includes logout/refresh/admin routes. |
| AUTH-04 / P0 | 1 / backend + QA | Enrollment security assertion fails after removing EnrollmentRequest. `EnrollmentRepository.has_access` permits free/category/same-tenant access. | Explicitly reconcile access policy and revocation with compatibility tests; prove revoked restricted entitlement denies submission/read/download. Reproduce on PostgreSQL. |
| ISO-01 / P0 | 0–1 / DB + QA | Live RLS modules are opt-in; CI does not enable their flag. Seven org_id models differ from central list. | Full migration run; every tenant table classified; real policies/grants inspected; non-owner A/B read/write, no-context, commit/retry/pool and worker tests. |
| REC-01 / P0 | 0 / operations | Restore drill verifies only `restore_probe`, not LMS backup. | Restore full synthetic LMS schema/data/media into isolated stack; verify tenant auth, enrolled versions, assignment files and grades; measured RPO/RTO. |
| DEV-01 / P1 | 0 / QA | This environment lacks Docker/PostgreSQL; Node here is 24 vs CI 20. | Run CI's exact toolchains, disposable PostgreSQL migration up/down/up and complete regression suite. Track skips as missing evidence. |
| API-01 / P1 | 0 / backend | OpenAPI reports duplicate learning-path operation ID. | Unique schema operation IDs; generated client contract remains compatible. |
| ID-01 / P1 | 2 / backend + product | User is tenant-scoped; Membership suggests multi-org identity. Teams and job roles absent. | Additive migrations/backfill; unique tenant employee IDs; cross-tenant manager/team refs rejected; idempotent import; joiner/mover/leaver contract. |
| TRAIN-01 / P1 | 3 / backend | Learning paths exist without job-role assignment rules. | Versioned previews, idempotent apply/outbox, correct QA/Marketing paths, retries and move history preserved. |
| READY-01 / P1 | 4 / backend + product | `assignment_service.py` completes blocks on submission; instructor approval is reserved in completion policy. | Separate submission/completion/verified competency; versioned rubric and authorized reviewer; final readiness AND gates. |
| KNOW-01 / P0 before AI | 5 / backend + security | Snapshot resolver falls back to live drafts. No approved knowledge ACL model. | Approved effective versions only; assessment keys/drafts/private evidence excluded; tenant+document ACL; immediate withdrawal/ACL revocation even during index failure. |
| BOT-01 / P1 | 6 / AI + backend | No dedicated RAG/chat module. | Read-only authenticated assistant; pre-retrieval ACLs and generation recheck; verified citations; abstention; bounded approved provider adapter; protected history/cache/logs. |
| EVAL-01 / P0 before AI pilot | 7 / QA + security | No assistant adversarial suite or grounded-answer evaluation. | Cross-tenant/team/citation, prompt-injection, revoked/expired sources, stale cache, unsupported/conflicting questions and dependency failure tests. Defined quality gates and tenant kill switch. |
| DATA-01 / P1 | later / backend | Learning-path analytics returns fixed values; payment verification returns enrollment success without enrollment; platform admin reset returns mock success; publication restore is mocked. | Replace each with real authorized behavior or explicit unavailable response; verify side effects and retries. No simulated success in customer workflows. |
| MOODLE-01 / P1 | 0 / product + operations | README/Compose describe Moodle; authoring comments retire sync. | Verify actual deployment dependency and document contract before removing or changing integration. |
| OPS-01 / P1 | later / operations | Entitlements, audited support access, SSO, retention and full observability need definition. | Tenant-scoped subscriptions; support grants expiring/audited; offboarding; retention/export/delete; monitored incidents and recovery. |

## Smallest corrective task for current failing evidence

Run `test_assignment_submit_requires_enrollment` against disposable PostgreSQL,
then define which grants authorize assignment access. Explicit enrollment deletion
currently does not override same-tenant/free-course access. Add restricted-course
revocation tests alongside compatibility tests for permitted free and legacy category
access. Do not weaken the assertion or disable the security suite to clear the gate.

The other observed failure, `test_assignment_actor_context_sets_rls_claims`, calls
PostgreSQL `current_setting` and cannot establish behavior on SQLite. Run it on real
PostgreSQL; classify it as unsupported supplemental test evidence, not a product fix.
