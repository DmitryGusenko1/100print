"""Download/extract private Ubuntu PostgreSQL binaries; no apt install or system changes."""
from pathlib import Path
import subprocess
ROOT=Path('/opt/ceo-orchestrator')
packages=ROOT/'data/postgres-packages'
dist=ROOT/'data/postgres-dist'
if dist.exists():
    raise SystemExit('Private distribution already exists; refusing overwrite')
packages.mkdir(exist_ok=True)
subprocess.run(['apt','download','postgresql-16','postgresql-client-16','postgresql-16-pgvector','libpq5'],cwd=packages,check=True)
dist.mkdir()
for package in packages.glob('*.deb'):
    subprocess.run(['dpkg-deb','-x',str(package),str(dist)],check=True)
print('Private PostgreSQL binaries ready. Run scripts/bootstrap_db.py once.')
