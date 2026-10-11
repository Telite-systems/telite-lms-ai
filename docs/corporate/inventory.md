# Baseline route, model and migration inventory

Generated from baseline `f5afafe6623314cd6fbb397262dbb4ee7419d19a` on 11 October 2026.

Development OpenAPI registration: 198 paths / 232 operations. ORM registration: 70 tables.
No request execution or live DB policy inspection is implied.

## ORM tables

An org_id column or central RLS listing is not proof of a working policy. Individual
migrations can install policies outside the central helper. Inspect the live DB.

| Table | Primary key | org_id | Central RLS list |
|---|---|---|---|
| `activity_log` | id | yes | yes |
| `allowed_domains` | domain | yes | no |
| `announcement_audiences` | id | yes | yes |
| `announcement_read_states` | id | yes | yes |
| `announcements` | id | yes | yes |
| `assignment_submissions` | id | yes | no |
| `audit_log` | id | yes | yes |
| `auth_sessions` | id | yes | yes |
| `builder_activity_log` | id | yes | yes |
| `categories` | id | yes | yes |
| `certificates` | id | yes | yes |
| `completion_rules` | id | yes | yes |
| `course_edit_locks` | course_id | yes | yes |
| `course_grades` | id | yes | yes |
| `course_modules` | id | yes | yes |
| `course_progress` | id | yes | yes |
| `course_reviews` | id | yes | yes |
| `course_sections` | id | yes | yes |
| `course_versions` | id | yes | yes |
| `courses` | id | yes | yes |
| `enrollment_requests` | id | yes | yes |
| `grade_categories` | id | yes | yes |
| `grade_change_audit` | id | yes | yes |
| `grade_items` | id | yes | yes |
| `grade_results` | id | yes | yes |
| `grading_events` | id | yes | yes |
| `grading_rubrics` | id | yes | yes |
| `grading_schemes` | id | yes | yes |
| `interactive_tracking` | id | yes | yes |
| `learner_activity_log` | id | yes | yes |
| `learner_events` | id | yes | yes |
| `learning_path_courses` | path_id, course_id | yes | yes |
| `learning_path_progress` | id | yes | yes |
| `learning_paths` | id | yes | yes |
| `lesson_block_progress` | id | yes | yes |
| `lesson_blocks` | id | yes | yes |
| `media_asset_usages` | id | yes | no |
| `media_assets` | id | yes | yes |
| `memberships` | id | yes | yes |
| `module_progress` | id | yes | yes |
| `notifications` | id | yes | yes |
| `org_invitations` | id | yes | yes |
| `organization_branding` | id | yes | yes |
| `organizations` | id | no | no |
| `pal_quiz_scores` | id | yes | yes |
| `pal_recommendations` | id | yes | yes |
| `pal_topic_performance` | id | yes | yes |
| `password_reset_tokens` | id | yes | yes |
| `pending_verifications` | id | yes | yes |
| `platform_settings` | id | no | no |
| `progression_rules` | id | yes | no |
| `question_banks` | id | yes | yes |
| `question_categories` | id | yes | yes |
| `question_import_jobs` | id | yes | yes |
| `question_tag_map` | question_version_id, tag_id | yes | yes |
| `question_tags` | id | yes | yes |
| `question_versions` | id | yes | yes |
| `questions` | id | yes | yes |
| `quiz_answers` | id | yes | yes |
| `quiz_attempt_events` | id | yes | yes |
| `quiz_attempt_questions` | id | yes | yes |
| `quiz_attempts` | id | yes | yes |
| `role_permissions` | id | yes | yes |
| `rubric_criteria` | id | yes | yes |
| `task_assignments` | id | yes | no |
| `task_reviews` | id | yes | no |
| `task_submissions` | id | yes | no |
| `tasks` | id | yes | yes |
| `users` | id | yes | yes |

## Migration graph

One Alembic head reported: `i1j2k3l4m5n6`. This is graph inspection only.

| File | Revision | Parent(s) |
|---|---|---|
| `000_bootstrap_foundation.py` | `000_bootstrap` | `None` |
| `001_phase3_initial.py` | `001_phase3` | `000_bootstrap` |
| `0e000a2a9613_add_assignment_submissions_table.py` | `0e000a2a9613` | `c1669e51aea9` |
| `2b803db5bf76_phase_d_quiz_engine.py` | `2b803db5bf76` | `417f828b3e0a` |
| `3ac877a47511_add_source_type_and_source_id_to_.py` | `3ac877a47511` | `57d2868d07e4` |
| `3ad32707e699_add_course_module_tables_phase_b.py` | `3ad32707e699` | `001_phase3` |
| `417f828b3e0a_phase_c_native_course_builder.py` | `417f828b3e0a` | `3ad32707e699` |
| `57d2868d07e3_phase_b1_question_bank_foundation.py` | `57d2868d07e3` | `cp_enrolled_version_20260620` |
| `57d2868d07e4_align_course_versions_snapshot_schema.py` | `57d2868d07e4` | `57d2868d07e3` |
| `8d1f3a9c4b20_add_question_import_metadata.py` | `8d1f3a9c4b20` | `3ac877a47511` |
| `9b2c7f4d1a6e_add_question_version_timestamps.py` | `9b2c7f4d1a6e` | `8d1f3a9c4b20` |
| `a1b2c3d4e5f6_add_media_asset_metadata.py` | `a1b2c3d4e5f6` | `f0d1c2b3a4e5` |
| `a5f001_platform_schema_normalization.py` | `a5f001` | `a1b2c3d4e5f6` |
| `a5f0025_add_branding_tables.py` | `a5f0025` | `a5f002` |
| `a5f002_normalize_tasks_table.py` | `a5f002` | `a5f001` |
| `a5f003_tenant_rls_rollout.py` | `a5f003` | `a5f0025` |
| `a5f004_schema_type_alignment.py` | `a5f004` | `a5f003` |
| `a5f005_restore_timestamp_defaults.py` | `a5f005` | `a5f004` |
| `a5f006_classify_remaining_tables.py` | `a5f006` | `a5f005` |
| `a5f007_rewrite_rls_policies_safe_context.py` | `a5f007` | `a5f006` |
| `a5f008_task_workflow_tables.py` | `a5f008` | `a5f007` |
| `a5f009_add_media_asset_metadata_json.py` | `a5f009` | `a5f008` |
| `add_section_progress_table.py` | `i1j2k3l4m5n6` | `h1e2f3g4h5i6` |
| `assignment_v1_20260620_native_assignment_engine.py` | `assignment_v1_20260620` | `theme_pref_20260619` |
| `assignment_v1_rls_force_20260620.py` | `assignment_v1_rls_force_20260620` | `assignment_v1_20260620` |
| `b2d976c3de97_phase_g_add_org_id_to_password_reset.py` | `b2d976c3de97` | `e40fc4255652` |
| `b7e2c4f91d33_add_question_version_category.py` | `b7e2c4f91d33` | `9b2c7f4d1a6e` |
| `c1669e51aea9_add_assignment_submissions_table.py` | `c1669e51aea9` | `a5f009` |
| `c2ea96aea04a_add_builder_tables.py` | `c2ea96aea04a` | `db5ba62f5025` |
| `c8f2a9e4d101_announcement_runtime.py` | `c8f2a9e4d101` | `b7e2c4f91d33` |
| `c99c89b4b321_media_asset_usages.py` | `c99c89b4b321` | `g7c9d4e1f236` |
| `cp_enrolled_version_20260620.py` | `cp_enrolled_version_20260620` | `assignment_v1_rls_force_20260620` |
| `d4f6a1b2c3e7_gradebook_g0_1_foundation.py` | `d4f6a1b2c3e7` | `c8f2a9e4d101` |
| `db5ba62f5025_phase_e_scorm_certs_analytics.py` | `db5ba62f5025` | `2b803db5bf76` |
| `e40fc4255652_phase_f_progress_models.py` | `e40fc4255652` | `c2ea96aea04a` |
| `e5a7b2c9d014_gradebook_g0_2_grade_results.py` | `e5a7b2c9d014` | `d4f6a1b2c3e7` |
| `f0d1c2b3a4e5_add_course_reviews.py` | `f0d1c2b3a4e5` | `b2d976c3de97` |
| `f6b8c3d0e125_gradebook_g0_3_course_grades.py` | `f6b8c3d0e125` | `e5a7b2c9d014` |
| `g7c9d4e1f236_gradebook_g0_4_completion_rules.py` | `g7c9d4e1f236` | `f6b8c3d0e125` |
| `h1e2f3g4h5i6_progression_rules.py` | `h1e2f3g4h5i6` | `h8d2e5f9a642` |
| `h8d2e5f9a641_gradebook_g0_6_grade_change_audit.py` | `h8d2e5f9a641` | `c99c89b4b321` |
| `h8d2e5f9a642_add_org_invitations_metadata_json.py` | `h8d2e5f9a642` | `h8d2e5f9a641` |
| `onboarding_username_1_add_username_to_onboarding.py` | `onboarding_username_1` | `0e000a2a9613` |
| `onboarding_username_2_add_status_constraint.py` | `onboarding_username_2` | `onboarding_username_1` |
| `onboarding_username_3_add_unique_username.py` | `onboarding_username_3` | `onboarding_username_2` |
| `theme_pref_20260619_add_user_theme_preference.py` | `theme_pref_20260619` | `onboarding_username_3` |

## Registered API paths

Generated using `create_app().openapi()` in development without app lifespan or
external services. Duplicate operation-ID warning is recorded in validation.md.

| Path | Methods |
|---|---|
| `/` | GET |
| `/admins` | GET, POST |
| `/admins/invite` | POST |
| `/admins/{user_id}` | DELETE, PATCH |
| `/api/admin/organizations/{org_id}/branding/draft` | GET, POST |
| `/api/admin/organizations/{org_id}/branding/history` | GET |
| `/api/admin/organizations/{org_id}/branding/publish` | POST |
| `/api/admin/organizations/{org_id}/branding/rollback/{version_id}` | POST |
| `/api/admin/organizations/{org_id}/branding/upload/{asset_type}` | POST |
| `/api/certificates/{course_id}` | GET |
| `/api/certificates/{course_id}/download` | GET |
| `/api/certificates/{course_id}/issue` | POST |
| `/api/invitations/{token}/validate` | GET |
| `/api/platform/admins` | GET |
| `/api/platform/admins/invitations` | GET |
| `/api/platform/admins/invitations/{invitation_id}` | DELETE |
| `/api/platform/admins/invitations/{invitation_id}/resend` | POST |
| `/api/platform/admins/invite` | POST |
| `/api/platform/admins/{user_id}` | DELETE |
| `/api/platform/admins/{user_id}/reset-password` | POST |
| `/api/platform/admins/{user_id}/status` | PATCH |
| `/api/platform/analytics/alerts` | POST |
| `/api/platform/analytics/export` | GET |
| `/api/platform/analytics/org/{org_id}` | GET |
| `/api/platform/analytics/overview` | GET |
| `/api/platform/audit` | GET |
| `/api/platform/audit/export` | GET |
| `/api/platform/features` | GET |
| `/api/platform/features/{org_id}` | PATCH |
| `/api/platform/invitations/accept` | POST |
| `/api/platform/organizations` | GET, POST |
| `/api/platform/organizations/{org_id}` | GET, PATCH |
| `/api/platform/organizations/{org_id}/status` | PATCH |
| `/api/public/branding/{tenant_slug}` | GET |
| `/api/public/branding/{tenant_slug}/health` | GET |
| `/api/v1/admin/assignments/{block_id}/submissions` | GET |
| `/api/v1/admin/gradebook/course-grades/{course_grade_id}/audit` | GET |
| `/api/v1/admin/gradebook/course-grades/{course_grade_id}/lock` | POST |
| `/api/v1/admin/gradebook/course-grades/{course_grade_id}/override` | POST |
| `/api/v1/admin/gradebook/course-grades/{course_grade_id}/release` | POST |
| `/api/v1/admin/gradebook/courses/{course_id}/course-grades` | GET |
| `/api/v1/admin/submissions/{submission_id}` | GET |
| `/api/v1/admin/submissions/{submission_id}/grade` | POST |
| `/api/v1/announcements` | GET, POST |
| `/api/v1/announcements/my` | GET |
| `/api/v1/announcements/{announcement_id}` | DELETE, GET, PATCH |
| `/api/v1/announcements/{announcement_id}/read` | PATCH |
| `/api/v1/audit-logs` | GET |
| `/api/v1/audit-logs/export` | GET |
| `/api/v1/enrol/bulk/execute` | POST |
| `/api/v1/enrol/bulk/preview` | POST |
| `/api/v1/enrol/manual` | POST |
| `/api/v1/learner/assignments/{block_id}/draft` | PATCH |
| `/api/v1/learner/assignments/{block_id}/resubmit` | POST |
| `/api/v1/learner/assignments/{block_id}/submission` | GET |
| `/api/v1/learner/assignments/{block_id}/submit` | POST |
| `/api/v1/learner/blocks/{block_id}/poll-results` | GET |
| `/api/v1/learner/blocks/{block_id}/poll/vote` | POST |
| `/api/v1/learner/blocks/{block_id}/quiz/submit` | POST |
| `/api/v1/learner/blocks/{block_id}/resources/{asset_id}/download` | GET |
| `/api/v1/learner/courses` | GET |
| `/api/v1/learner/courses/{course_id}/module-progress` | GET |
| `/api/v1/learner/courses/{course_id}/submit` | POST |
| `/api/v1/learner/courses/{id}` | GET |
| `/api/v1/learner/events` | POST |
| `/api/v1/learner/gradebook/courses/{course_id}/final-grade` | GET |
| `/api/v1/learner/heartbeat` | POST |
| `/api/v1/learner/modules/{id}` | GET |
| `/api/v1/learner/paths` | GET |
| `/api/v1/learner/paths/{id}` | GET |
| `/api/v1/learner/progress` | POST |
| `/api/v1/learner/resume/{course_id}` | GET |
| `/api/v1/learner/validate-access` | POST |
| `/api/v1/notifications` | GET |
| `/api/v1/notifications/read-all` | POST |
| `/api/v1/notifications/unread-count` | GET |
| `/api/v1/notifications/{notification_id}/read` | PATCH |
| `/api/v1/player/h5p/{asset_id}` | GET |
| `/api/v1/player/h5p/{asset_id}/versions/{asset_version}` | GET |
| `/api/v1/player/h5p/{asset_id}/versions/{asset_version}/{file_path}` | GET |
| `/api/v1/player/h5p/{asset_id}/{file_path}` | GET |
| `/api/v1/player/modules/{module_id}/launch` | GET |
| `/api/v1/player/tracking` | POST |
| `/api/v1/question-banks` | GET, POST |
| `/api/v1/question-banks/categories` | GET, POST |
| `/api/v1/question-banks/categories/{category_id}` | DELETE, PUT |
| `/api/v1/question-banks/check-stale` | POST |
| `/api/v1/question-banks/imports` | POST |
| `/api/v1/question-banks/questions` | GET |
| `/api/v1/question-banks/tags` | GET, POST |
| `/api/v1/question-banks/tags/{tag_id}` | DELETE, PUT |
| `/api/v1/question-banks/{bank_id}` | GET |
| `/api/v1/question-banks/{bank_id}/questions` | GET, POST |
| `/api/v1/question-banks/{bank_id}/questions/{q_id}/draft` | DELETE, PUT |
| `/api/v1/question-banks/{bank_id}/questions/{q_id}/drafts` | POST |
| `/api/v1/question-banks/{bank_id}/questions/{q_id}/publish` | POST |
| `/api/v1/question-banks/{bank_id}/questions/{q_id}/versions` | GET |
| `/api/v1/submissions/{submission_id}/download` | GET |
| `/auth/forgot-password` | POST |
| `/auth/login` | POST |
| `/auth/logout` | POST |
| `/auth/me` | GET |
| `/auth/preferences/theme` | PATCH |
| `/auth/refresh` | POST |
| `/auth/reset-password` | POST |
| `/auth/sessions/` | DELETE, GET |
| `/auth/sessions/add-account` | POST |
| `/auth/sessions/admin/{user_id}` | DELETE |
| `/auth/sessions/switch-account` | POST |
| `/auth/sessions/switch-org` | POST |
| `/auth/sessions/{session_id}` | DELETE |
| `/authoring/courses/{course_id}/blocks` | PUT |
| `/authoring/courses/{course_id}/builder` | GET |
| `/authoring/courses/{course_id}/heartbeat` | POST |
| `/authoring/courses/{course_id}/lock` | DELETE, POST |
| `/authoring/courses/{course_id}/modules/{module_id}/blocks` | GET |
| `/authoring/courses/{course_id}/progression-rules` | GET, POST |
| `/authoring/courses/{course_id}/publish` | POST |
| `/authoring/courses/{course_id}/sections` | POST |
| `/authoring/courses/{course_id}/sections/{section_id}` | DELETE, PATCH |
| `/authoring/courses/{course_id}/sections/{section_id}/duplicate` | POST |
| `/authoring/courses/{course_id}/structure` | PUT |
| `/authoring/courses/{course_id}/validate` | GET |
| `/authoring/courses/{course_id}/versions` | POST |
| `/authoring/learning-paths` | GET, POST |
| `/authoring/learning-paths/{path_id}` | DELETE, GET, PUT |
| `/authoring/learning-paths/{path_id}/analytics` | GET |
| `/authoring/learning-paths/{path_id}/courses` | PUT |
| `/authoring/learning-paths/{path_id}/sequence` | POST |
| `/authoring/media` | GET |
| `/authoring/media/h5p/{asset_id}/{file_path}` | GET |
| `/authoring/media/presigned-url` | POST |
| `/authoring/media/upload` | POST |
| `/authoring/media/upload-url` | POST |
| `/authoring/media/{asset_id}` | DELETE, PATCH |
| `/authoring/media/{asset_id}/confirm` | PUT |
| `/authoring/media/{asset_id}/replace` | POST |
| `/authoring/media/{asset_id}/usage` | GET |
| `/authoring/modules` | POST |
| `/authoring/modules/quiz/questions` | POST |
| `/authoring/modules/{module_id}` | DELETE, PUT |
| `/authoring/modules/{module_id}/blocks` | POST |
| `/authoring/modules/{module_id}/blocks/order` | PUT |
| `/authoring/modules/{module_id}/duplicate` | POST |
| `/authoring/permissions` | GET, PUT |
| `/authoring/progression-rules/{rule_id}` | DELETE, PUT |
| `/authoring/publishing/courses/{course_id}/reviews` | GET |
| `/authoring/publishing/courses/{course_id}/versions` | GET, POST |
| `/authoring/publishing/courses/{course_id}/versions/{left_version_id}/compare/{right_version_id}` | GET |
| `/authoring/publishing/courses/{course_id}/versions/{version_id}/restore` | POST |
| `/authoring/publishing/courses/{course_id}/workflow` | POST |
| `/categories` | GET, POST |
| `/categories/{category_id}` | DELETE, PATCH |
| `/categories/{category_slug}/courses` | GET, POST |
| `/categories/{category_slug}/courses/{course_id}` | DELETE, PATCH |
| `/courses/{course_id}/launch` | GET |
| `/dashboard/categories/{category_slug}/admin` | GET |
| `/dashboard/categories/{category_slug}/grading-analytics` | GET |
| `/dashboard/categories/{category_slug}/stats` | GET |
| `/dashboard/learner` | GET |
| `/dashboard/learner/grading-analytics` | GET |
| `/dashboard/super-admin` | GET |
| `/dashboard/super-admin/grading-analytics` | GET |
| `/enrol/requests` | GET |
| `/enrol/requests/approve-batch` | POST |
| `/enrol/requests/{request_id}/approve` | POST |
| `/enrol/requests/{request_id}/reject` | POST |
| `/enrol/self` | POST |
| `/health` | GET |
| `/health/liveness` | GET |
| `/health/readiness` | GET |
| `/learners/invite` | POST |
| `/learners/reinvite/{invitation_id}` | POST |
| `/metrics` | GET |
| `/notifications` | GET |
| `/pal/compute` | POST |
| `/pal/distribution/{category_slug}` | GET |
| `/pal/leaderboard/{category_slug}` | GET |
| `/pal/users/{user_id}` | GET |
| `/payment/courses` | GET |
| `/payment/create-order` | POST |
| `/payment/verify-and-enrol` | POST |
| `/public/verify/{token}` | GET |
| `/settings/domains` | POST |
| `/settings/domains/{domain}` | DELETE |
| `/settings/system` | GET |
| `/signup/organizations` | GET |
| `/tasks` | GET, POST |
| `/tasks/{task_id}` | DELETE, PATCH |
| `/tasks/{task_id}/review` | POST |
| `/tasks/{task_id}/start` | POST |
| `/tasks/{task_id}/submit` | POST |
| `/tasks/{task_id}/submit-work` | POST |
| `/users` | GET |
| `/users/{user_id}` | DELETE, GET |
| `/users/{user_id}/activate` | PATCH |
| `/users/{user_id}/activity` | GET |
| `/users/{user_id}/role` | PATCH |
