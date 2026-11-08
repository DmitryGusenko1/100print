#!/bin/sh
# Fail closed for every caller, including Hermes app-server and delegated CLI.
# No prompt, argument, environment flag or approval marker can reopen this route.
printf '%s\n' 'issue23: Codex delegation paused pending verified runtime isolation' >&2
exit 77
