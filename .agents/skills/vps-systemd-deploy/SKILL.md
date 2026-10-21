---
name: vps-systemd-deploy
description: Deploys and operates 100print services on a VPS using systemd and virtual environments, without Docker unless requirements explicitly change.
---

# VPS + systemd Deploy

Use for deployment, service management, ports, logs, healthchecks, backups, and rollback.

## Before changing anything
Inspect existing users, services, ports, Python environments, databases, reverse proxies, and bot processes. Do not assume GitHub access implies VPS access.

## Deployment model
- Dedicated application directory.
- Dedicated Python virtual environment.
- Environment file outside Git.
- systemd service with explicit user, working directory, restart policy, and logging.
- HTTP service listens on localhost by default.
- Public exposure only through authenticated HTTPS reverse proxy when required.

## Rules
- Do not disrupt unrelated sites, bots, or services.
- Never launch a second polling process with the same Telegram bot token.
- Check configuration before restart.
- After restart verify service status, logs, health endpoint, and the critical user path.
- Keep a rollback path for code and schema changes.

## Result
Report actual service state and checks, not assumed success.
