# Corporate LMS and knowledge-assistant threat model

Draft for engineering review, 11 October 2026. Applies to the reviewed native LMS
and proposed corporate assistant. The assistant is not yet implemented.

## Protected assets and trust boundaries

Protect employee identity/sessions, membership and capabilities, courses and published
versions, restricted procedures, submissions/answer keys, grades/readiness decisions,
conversation history, embeddings, tenant audits, provider credentials and recovery
backups. Tenant isolation includes metadata and existence, not just document bodies.

Boundaries: browser/API -> authenticated backend; backend -> current membership and
capability policy; backend/worker -> PostgreSQL under non-owner tenant context;
upload -> quarantine/parser -> approved index; authorized retrieval -> external model
provider; citation/history/export -> reauthorization; Git/CI -> deployment credentials;
backup storage -> restore environment. Platform support access needs separate expiring
approval and audit; being platform admin must not routinely expose tenant knowledge.

## Abuse cases, controls and verification

| Threat | Current evidence / proposed control | Verification |
|---|---|---|
| Stale JWT retains revoked privileges | Current authority uses token claims. Resolve current session, membership, user and tenant before any tenant action. | Old JWT after suspension/demotion/disable/logout; invalid tenant switch; no revealing errors. |
| Explicit deny restored by fallback | Reproduced role fallback; consolidate deny-precedence policy. | Default role allows but tenant override denies at every guard. |
| Cross-tenant or cross-team data access | RLS helpers/migrations exist; use non-owner role, scoped queries and tenant-consistent refs. | A/B reads/writes, missing context, worker retry and connection reuse; policies and bypass grants inspected. |
| Restricted course access survives entitlement revocation | Supplemental enrollment assertion fails; broad same-tenant/free access exists. | Reconcile grants; restricted revocation denies assignment/read/download, while approved public/free compatibility stays explicit. |
| Cookie mutation forgery | CSRF dependency wiring unproven; require valid pair for cookie-auth mutations. | Missing cookie/header/wrong value denies; valid pair passes; bearer-only policy tested. |
| Sensitive archive committed to Git | Private archive inspection found env/dumps/key markers. Remove tracked copies; ignore+CI source gate; rotate/review exposure and coordinate history remediation. | Forced ignored archive fails CI; all-history redacted scans; operator evidence of rotation and restricted backups. |
| Draft, answer-key or revoked document used as evidence | Snapshot live-draft fallback exists; assistant must use separate approved eligibility/ACL path. | Draft/assessment key never indexed/retrieved; withdraw/expire/ACL change blocks immediately while jobs are delayed. |
| Prompt injection via question or document | Treat all content as untrusted data; model has no tools or authority; isolate provider adapter. | Requests to dump secrets, override ACLs, run SQL or follow document instructions refuse/abstain; no forbidden provider payload. |
| Retrieval or citation discloses hidden metadata | ACL predicate before ranking/model calls; reauthorize candidates and citation opens. | Restricted titles/existence/citations and history remain non-disclosing after revocation. |
| Unsupported or outdated policy answer | Evidence-only structured answers with effective-version and citation validation. | Unknown/conflicting questions abstain; replacement excludes stale current-policy answers; historic training versions explicitly labeled. |
| Cache/log/embedding leaks | Tenant/actor/ACL-version scope; minimal logs and retention; protect all derived stores. | Cross-user/tenant cache probes, export authorization, log redaction and retention deletion. |
| Parser malware/SSRF or resource exhaustion | Quarantine, size/type limits, sandboxed parsing; no arbitrary URL fetch; retry/time/cost limits. | Malformed/oversized uploads and network targets fail safely; jobs idempotent; no index before approval. |
| False employee readiness | Submission is currently block completion; add versioned evidence and authorized rubric review. | AI feedback, time watched or submission alone cannot mark ready; reviewer scope and immutable decision audit. |
| Recovery or billing reports false success | Current restore probe and multiple mock-success paths are insufficient. | Full LMS restore measured; payment persists genuine entitlement; reset delivery and snapshot restoration tested or declared unavailable. |

## Assistant request contract

Authenticate and resolve current authority; retrieve only currently authorized,
approved effective content; reauthorize before generation; send minimum excerpts
only to an operator-approved provider; validate all evidence IDs and citations;
render sanitized text; abstain without exposing restricted titles. It may not execute
SQL, grant access, send messages, enroll employees or determine readiness.

Withdrawal/offboarding fail closed independently of index cleanup. Provider or index
failure returns explicit unavailability, not invented policy. Preserve required
training evidence separately from operational chat retention. Define retention,
provider data-handling terms, permitted classifications and audit ownership before
customer ingestion; do not assume one tenant's approval covers another tenant.

## Residual risks and launch gates

History copies and credential exposure remain after branch deletion. Scanner results
can miss compressed/encrypted content and are not proof of rotation. SQLite tests
cannot validate RLS. Platform bypass settings are privileged application mechanisms,
not protection against arbitrary SQL by the same DB role. Valid citations do not by
themselves prove every answer claim is supported: evaluate claim grounding too.

Owners must approve the unresolved identity/Moodle/enrollment contracts, complete
non-owner PostgreSQL and recovery evidence, address actual failures, and run the AI
adversarial suite before a corporate pilot. Stage 0 currently remains blocked; no
zero-failure or zero-leak guarantee is made.
