#!/usr/bin/python3
"""Administrator-installed fixed-action helper. No arbitrary unit names or paths."""
import os
import subprocess
import sys

UNITS=('ceo-orchestrator.service','ceo-telegram-bot.service','ceo-chatgpt-api.service','ceo-github-watcher.service')

def command(args):
    if len(args)!=2 or args[0] not in ('restart','status') or args[1] not in UNITS:
        raise ValueError('Expected restart|status and an allowlisted project unit')
    return ['/usr/bin/systemctl',args[0],args[1],'--no-pager']

if __name__=='__main__':
    try: cmd=command(sys.argv[1:])
    except ValueError as error: raise SystemExit(str(error))
    if os.geteuid()!=0: raise SystemExit('Administrator installation required; no privilege escalation attempted')
    os.chdir('/')
    raise SystemExit(subprocess.run(cmd,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C'},timeout=60).returncode)
