#!/bin/sh
set -eu
umask 077
export LD_LIBRARY_PATH=/opt/ceo-orchestrator/data/postgres-dist/usr/lib/x86_64-linux-gnu
exec /opt/ceo-orchestrator/data/postgres-dist/usr/lib/postgresql/16/bin/postgres -D /opt/ceo-orchestrator/ai-team/runtime/pgdata
