#!/bin/bash
set -euo pipefail

mkdir -p /app/uploads
if [ "$(id -u)" -eq 0 ]; then
    chown -R telite:telite /app/uploads
    exec gosu telite "$0" "$@"
fi

if [[ "${1:-}" == "uvicorn" || "${*:-}" == *"uvicorn app.main:app"* ]]; then
    echo "Preparing runtime database role..."
    python -m scripts.ensure_runtime_db_role
    echo "Preparing database schema..."
    python -m scripts.run_migrations
fi

# Runtime API and workers must use the non-owner role. Strip the bootstrap
# migration/owner credentials from their inherited environment when configured.
if [[ -n "${TELITE_RUNTIME_POSTGRES_USER:-}" && -n "${TELITE_RUNTIME_POSTGRES_PASSWORD:-}" ]]; then
    export TELITE_POSTGRES_USER="$TELITE_RUNTIME_POSTGRES_USER"
    export TELITE_POSTGRES_PASSWORD="$TELITE_RUNTIME_POSTGRES_PASSWORD"
    unset TELITE_MIGRATION_DATABASE_URL POSTGRES_USER POSTGRES_PASSWORD
fi

unset TELITE_DB_CONNECTION_PURPOSE
exec "$@"
