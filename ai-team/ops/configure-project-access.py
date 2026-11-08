#!/usr/bin/env python3
"""Install the scoped Hermes wrapper and operating instructions, not global permissions."""
from pathlib import Path
import os
import yaml

ROOT = Path('/opt/ceo-orchestrator')
HOME = ROOT / 'ai-team/runtime/hermes-home'


def main():
    os.umask(0o077)
    path = HOME / 'config.yaml'
    config = yaml.safe_load(path.read_text())
    config.setdefault('model', {})['codex_bin'] = str(ROOT / 'ai-team/ops/hermes-codex-project.sh')
    temporary = path.with_suffix('.issue22.tmp')
    temporary.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    temporary.chmod(0o600)
    temporary.replace(path)
    soul = HOME / 'SOUL.md'
    soul.write_text((ROOT / 'ai-team/roles/hermes-soul.md').read_text())
    soul.chmod(0o600)
    print('Scoped Hermes project access configured; restart its user gateway to reload.')


if __name__ == '__main__':
    main()
