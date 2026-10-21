"""Fail-closed offline process adapter. Domain logic does not depend on Codex."""
import json
import logging
from pathlib import Path
import os
import signal
import subprocess
import tempfile
from app.db import ROOT

class CodexRunner:
    def __init__(self, executable, allowed_workdirs=()):
        self.executable = Path(executable).resolve(strict=True)
        self.allowed = [(ROOT/'jobs/workspaces').resolve(), *(Path(p).resolve(strict=True) for p in allowed_workdirs)]
        if not self.executable.is_relative_to(ROOT):
            raise ValueError('Executable must be installed inside project')

    def run(self, prompt, workdir=ROOT, timeout=60):
        wd = Path(workdir).resolve(strict=True)
        if not any(wd.is_relative_to(base) for base in self.allowed):
            raise ValueError('Workdir outside whitelist')
        if not 0 < timeout <= 300:
            raise ValueError('timeout must be in (0,300]')
        # Only the selected workspace is exposed; project env, auth and DB stay hidden.
        # External symlinks cannot escape the mount namespace. No host network.
        if wd == ROOT or any(wd.is_relative_to(ROOT/p) for p in ('data','.codex','.config','.venv','logs')):
            raise ValueError('Choose a dedicated workspace under jobs/, not the project root')
        command=['bwrap','--unshare-all','--die-with-parent','--new-session',
                 '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib',
                 '--ro-bind','/lib64','/lib64','--symlink','usr/bin','/bin',
                 '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
                 '--dir','/adapter','--ro-bind',str(self.executable),'/adapter/codex',
                 '--bind',str(wd),'/workspace','--chdir','/workspace',
                 '--clearenv','--setenv','PATH','/usr/bin:/bin',
                 '--setenv','HOME','/tmp','/adapter/codex']
        logging.info('codex start workdir=%s timeout=%s', wd, timeout)
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
            timed_out=False
            try:
                proc.communicate(prompt.encode(),timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out=True
                os.killpg(proc.pid,signal.SIGKILL)
                proc.communicate()
            out.seek(0); err.seek(0)
            result={'ok':proc.returncode==0 and not timed_out,'returncode':proc.returncode,
                    'timed_out':timed_out,'stdout':out.read(1048576).decode(errors='replace'),
                    'stderr':err.read(1048576).decode(errors='replace')}
        logging.info('codex finish returncode=%s timed_out=%s',proc.returncode,timed_out)
        json.dumps(result)
        return result
