#!/usr/bin/env python3
"""Install the interlock only in this project's Hermes CLI entrypoint."""
from pathlib import Path

ROOT = Path('/opt/ceo-orchestrator')
CLI = ROOT / 'ai-team/runtime/hermes-venv/bin/hermes'
HEADER = '#!/opt/ceo-orchestrator/ai-team/runtime/hermes-venv/bin/python\n'
BODY = '''import runpy
import sys
runpy.run_path('/opt/ceo-orchestrator/ai-team/ops/hermes-containment.py')
from hermes_cli.main import main
sys.exit(main())
'''
if CLI.is_symlink() or not CLI.resolve().is_relative_to(ROOT):
    raise SystemExit('Refusing non-project CLI')
CLI.write_text(HEADER + BODY)
CLI.chmod(0o755)
print('Project Hermes CLI containment installed; gateway reload required.')
