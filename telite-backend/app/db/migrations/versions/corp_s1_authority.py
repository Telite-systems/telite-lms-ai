"""Backfill legacy home memberships and enforce tenant RLS guard coverage.

Revision ID: corp_s1_authority
Revises: i1j2k3l4m5n6
"""

import sqlalchemy as sa
from alembic import op

revision = "corp_s1_authority"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    pg = conn.dialect.name == "postgresql"
    if pg:
        conn.execute(sa.text("SELECT set_config('app.bypass_rls', 'on', true)"))
    # Never overwrite a suspended or revoked existing membership. This one-time
    # data migration preserves legacy home roles; runtime has no fallback grant.
    conn.execute(sa.text("""
        INSERT INTO memberships (user_id, org_id, role, category_scope, status)
        SELECT u.id, u.org_id, u.role, u.category_scope,
               CASE WHEN u.is_active = true AND u.status = 'active' THEN 'active' ELSE 'suspended' END
        FROM users u JOIN organizations o ON o.id = u.org_id
        WHERE u.is_platform_admin = false AND u.role <> 'platform_admin'
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = u.id AND m.org_id = u.org_id)
    """))
    if not pg:
        return
    inspector = sa.inspect(conn)
    for table in inspector.get_table_names(schema="public"):
        columns = {c["name"] for c in inspector.get_columns(table, schema="public")}
        column = "org_id" if "org_id" in columns else (
            "organization_id" if table == "organization_branding" else None
        )
        if not column:
            continue
        quoted = conn.dialect.identifier_preparer.quote(table)
        predicate = (
            f"({column} = NULLIF(current_setting('app.current_org_id', true), '')::integer "
            "OR current_setting('app.bypass_rls', true) = 'on')"
        )
        conn.execute(sa.text(f"ALTER TABLE public.{quoted} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE public.{quoted} FORCE ROW LEVEL SECURITY"))
        # A restrictive tenant boundary cannot broaden actor-specific policies.
        conn.execute(sa.text(f"DROP POLICY IF EXISTS corporate_tenant_guard ON public.{quoted}"))
        conn.execute(sa.text(f"CREATE POLICY corporate_tenant_guard ON public.{quoted} AS RESTRICTIVE "
                             f"FOR ALL USING {predicate} WITH CHECK {predicate}"))
        permissive = conn.execute(sa.text("""
            SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = :table
              AND permissive = 'PERMISSIVE' LIMIT 1
        """), {"table": table}).scalar()
        if not permissive:
            conn.execute(sa.text(f"CREATE POLICY corporate_tenant_access ON public.{quoted} "
                                 f"FOR ALL USING {predicate} WITH CHECK {predicate}"))
    conn.execute(sa.text("SELECT set_config('app.bypass_rls', 'off', true)"))


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in sa.inspect(conn).get_table_names(schema="public"):
        quoted = conn.dialect.identifier_preparer.quote(table)
        conn.execute(sa.text(f"DROP POLICY IF EXISTS corporate_tenant_guard ON public.{quoted}"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS corporate_tenant_access ON public.{quoted}"))
    # Keep membership evidence and enabled/FORCE RLS; rollback must not reopen
    # owner bypass or erase identity data. Old code is compatible with these rows.
