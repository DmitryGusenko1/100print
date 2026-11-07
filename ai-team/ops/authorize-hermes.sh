#!/bin/bash
set -euo pipefail
umask 077
cd /opt/ceo-orchestrator
export HERMES_HOME=/opt/ceo-orchestrator/ai-team/runtime/hermes-home
ai-team/runtime/hermes-venv/bin/hermes auth add openai-codex --type oauth --no-browser
ai-team/runtime/hermes-venv/bin/python - <<'PY'
from pathlib import Path
from hermes_cli.auth_codex import resolve_codex_runtime_credentials
credentials = resolve_codex_runtime_credentials(read_only=True)
if not credentials.get('api_key'):
    raise SystemExit('Hermes authorization not present; no readiness marker written')
p = Path('data/ai-team-hermes-auth-ready')
temporary = p.with_suffix('.tmp')
temporary.write_text('Hermes OAuth stored; inference and Telegram handoff still require executor verification.\n')
temporary.chmod(0o600)
temporary.replace(p)
print('Hermes authorization saved. Executor may resume; Telegram readiness is not yet verified.')
PY
