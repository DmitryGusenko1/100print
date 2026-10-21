#!/bin/sh
# Future administrator-only installation. Executor must never run this script.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Administrator installation required'; exit 1; }
source_file=/opt/ceo-orchestrator/scripts/project_service_helper.py
helper=/usr/local/sbin/ceo-project-service
rule=/etc/sudoers.d/ceo-project-service
[ ! -e "$helper" ] && [ ! -e "$rule" ] || { echo 'Existing installation; review manually'; exit 1; }
[ ! -L /usr/local/sbin ] && [ ! -L /etc/sudoers.d ] || exit 1
# A root reviewer must verify this source before invocation.
install -o root -g root -m 0755 "$source_file" "$helper"
temporary=$(mktemp /etc/sudoers.d/.ceo-project-service.XXXXXX)
trap 'rm -f "$temporary"' EXIT
printf '%s\n' 'ceoorch ALL=(root) NOPASSWD: /usr/local/sbin/ceo-project-service restart ceo-orchestrator.service, /usr/local/sbin/ceo-project-service restart ceo-telegram-bot.service, /usr/local/sbin/ceo-project-service restart ceo-chatgpt-api.service, /usr/local/sbin/ceo-project-service restart ceo-github-watcher.service' > "$temporary"
chmod 0440 "$temporary"
visudo -cf "$temporary"
chown root:root "$temporary"
mv "$temporary" "$rule"
echo 'Project helper installed; no services restarted'
