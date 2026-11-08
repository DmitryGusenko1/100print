#!/usr/bin/env python3
"""Copy only Python runtime/source, never execute the legacy runtime as root.

Called by the installer on the HOST. Does not write to the legacy project.
"""
import json
import os
from pathlib import Path
import stat
import sys
from urllib.parse import unquote, urlparse

LEGACY = Path('/opt/ceo-orchestrator/ai-team/runtime')
EXCLUDED = {'.git', '.env', '.venv', '__pycache__', 'auth.json', 'state.db',
            'sessions', 'logs', 'data', 'secrets', 'node_modules', 'tests', 'test', 'direct_url.json'}


def open_directory(path):
    # Walk declared source directories without following any symlink ancestor.
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.absolute().parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def copy_fd(source_fd, destination, owner):
    for name in os.listdir(source_fd):
        if name in EXCLUDED or name.startswith('.') or Path(name).suffix in ('.pth', '.pyc'):
            continue
        info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        target = destination / name
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=source_fd)
            try:
                target.mkdir(exist_ok=True, mode=0o755)
                copy_fd(child, target, owner)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=source_fd)
            with os.fdopen(fd, 'rb') as source:
                current = os.fstat(source.fileno())
                if not stat.S_ISREG(current.st_mode) or current.st_nlink > 1 and current.st_uid != owner:
                    raise RuntimeError('runtime foreign-owned hardlinks/special files refused')
                data = source.read()
            if target.exists() and target.read_bytes() != data:
                raise RuntimeError('runtime package collision: ' + str(target))
            target.write_bytes(data)
            target.chmod(0o644)
        else:
            raise RuntimeError('runtime symlinks/special files refused')


def copy_tree(source, destination):
    fd = open_directory(source)
    try:
        copy_fd(fd, destination, os.fstat(fd).st_uid)
    finally:
        os.close(fd)


def prepare(destination, legacy=LEGACY):
    if destination.exists():
        return
    packages = legacy / 'hermes-venv/lib' / ('python%d.%d' % sys.version_info[:2]) / 'site-packages'
    if not packages.resolve().is_relative_to(legacy.resolve()):
        raise RuntimeError('legacy packages escape selected runtime')
    if not packages.is_dir():
        raise RuntimeError('legacy Hermes Python ABI differs/missing; supply curated hermes-runtime for /usr/bin/python3')
    fd = open_directory(packages)
    os.close(fd)
    stage = destination.with_name('hermes-runtime.staging-' + str(os.getpid()))
    stage.mkdir(mode=0o755)
    # On a failed export keep staging for diagnosis, never publish a partial runtime.
    copy_tree(packages, stage)
    if not (stage / 'hermes_cli/main.py').exists():
        candidates = []
        for metadata in packages.glob('*.dist-info/direct_url.json'):
            fd = os.open(metadata, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise RuntimeError('unsafe editable runtime metadata')
                data = json.load(handle)
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
