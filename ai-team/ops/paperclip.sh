#!/bin/sh
set -eu
umask 077
cd /opt/ceo-orchestrator/ai-team
export PATH="/opt/ceo-orchestrator/ai-team/runtime/node/node_modules/node/bin:/opt/ceo-orchestrator/ai-team/runtime/hermes-venv/bin:/usr/bin:/bin"
export PAPERCLIP_HOME=/opt/ceo-orchestrator/ai-team/runtime/paperclip-home
export PAPERCLIP_CONFIG=/opt/ceo-orchestrator/ai-team/runtime/paperclip-config.json
export HERMES_HOME=/opt/ceo-orchestrator/ai-team/runtime/hermes-home
export HEARTBEAT_SCHEDULER_ENABLED=false
export PAPERCLIP_DEPLOYMENT_MODE=authenticated
export PAPERCLIP_BIND=loopback
export LD_LIBRARY_PATH=/opt/ceo-orchestrator/data/postgres-dist/usr/lib/x86_64-linux-gnu
set -a
. /opt/ceo-orchestrator/ai-team/runtime/service.env
set +a
exec node /opt/ceo-orchestrator/ai-team/runtime/paperclip/node_modules/paperclipai/dist/index.js run --config "$PAPERCLIP_CONFIG" --no-repair
