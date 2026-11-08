#!/usr/bin/env python3
"""Copy only Python runtime/source, never execute the legacy runtime as root.

Called by the installer on the HOST. Does not write to the legacy project.
"""
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import unquote, urlparse

LEGACY = Path('/opt/ceo-orchestrator/ai-team/runtime')
EXCLUDED = {'.git', '.env', '.venv', '__pycache__', 'auth.json', 'state.db',
            'sessions', 'logs', 'data', 'secrets', 'node_modules', 'tests', 'test'}


def copy_tree(source, destination):
    for item in source.iterdir():
        if item.name in EXCLUDED or item.name.startswith('.') or item.suffix in ('.pth', '.pyc'):
            continue
        if item.is_symlink():
            raise RuntimeError('legacy runtime contains symlink; curate manually: ' + str(item))
        target = destination / item.name
        if item.is_dir():
            target.mkdir(exist_ok=True, mode=0o755)
            copy_tree(item, target)
        elif item.is_file():
            if target.exists() and target.read_bytes() != item.read_bytes():
                raise RuntimeError('runtime package collision: ' + str(target))
            shutil.copyfile(item, target)
            target.chmod(0o644)
        else:
            raise RuntimeError('runtime special file refused')


def prepare(destination, legacy=LEGACY):
    if destination.exists():
        return
    packages = legacy / 'hermes-venv/lib' / ('python%d.%d' % sys.version_info[:2]) / 'site-packages'
    if not packages.resolve().is_relative_to(legacy.resolve()):
        raise RuntimeError('legacy packages escape selected runtime')
    if not packages.is_dir():
        raise RuntimeError('legacy Hermes Python ABI differs/missing; supply curated hermes-runtime for /usr/bin/python3')
    stage = destination.with_name('hermes-runtime.staging-' + str(os.getpid()))
    stage.mkdir(mode=0o755)
    # On a failed export keep staging for diagnosis, never publish a partial runtime.
    copy_tree(packages, stage)
    if not (stage / 'hermes_cli/main.py').exists():
        candidates = []
        for metadata in packages.glob('*.dist-info/direct_url.json'):
            data = json.loads(metadata.read_text())
            url = urlparse(data.get('url', ''))
            source = Path(unquote(url.path))
            if url.scheme != 'file':
                continue
            # Validate the boundary BEFORE inspecting files below an editable path.
            if not source.resolve().is_relative_to(legacy.resolve()):
                raise RuntimeError('editable source is outside the selected project runtime')
            if (source / 'hermes_cli/main.py').is_file():
                candidates.append(source)
        if len(candidates) != 1:
            raise RuntimeError('cannot locate unique editable Hermes source; supply curated hermes-runtime')
        copy_tree(candidates[0], stage)
    stage.rename(destination)
