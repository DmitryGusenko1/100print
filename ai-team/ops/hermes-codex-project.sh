#!/bin/sh
# Per-Hermes MCP only. Preserve Codex's sandbox and approval configuration.
set -eu
exec /usr/bin/codex \
  -c 'mcp_servers.ceo_project.command="/opt/ceo-orchestrator/.venv/bin/python"' \
  -c 'mcp_servers.ceo_project.args=["/opt/ceo-orchestrator/ai-team/ops/project-access.py"]' \
  -c 'mcp_servers.ceo_project.enabled_tools=["project_read","executor_probe"]' \
  -c 'mcp_servers.ceo_project.tools.project_read.approval_mode="approve"' \
  -c 'mcp_servers.ceo_project.tools.executor_probe.approval_mode="approve"' \
  "$@"
