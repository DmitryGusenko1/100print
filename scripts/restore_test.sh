#!/usr/bin/env bash
set -euo pipefail
: "${TEST_DATABASE_URL:?TEST_DATABASE_URL is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"
pg_restore --clean --if-exists --no-owner --dbname="$TEST_DATABASE_URL" "$BACKUP_FILE"
