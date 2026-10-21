"""Initialize an isolated PostgreSQL cluster entirely inside this checkout.

First unpack Ubuntu postgresql-16, postgresql-client-16 and postgresql-16-pgvector
and libpq5 packages into .runtime/postgres using apt download and dpkg-deb -x.
Never uses or changes system PostgreSQL clusters.
"""

import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
BIN = RUNTIME / "postgres/usr/lib/postgresql/16/bin"
SHARE = RUNTIME / "postgres/usr/share/postgresql/16"
LIB = RUNTIME / "postgres/usr/lib/postgresql/16/lib"
DATA = RUNTIME / "pgdata"
SOCKET = RUNTIME / "socket"


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    if DATA.exists() or (ROOT / ".env").exists():
        raise SystemExit("Refusing to overwrite an existing cluster or .env")
    os.environ["LD_LIBRARY_PATH"] = str(RUNTIME / "postgres/usr/lib/x86_64-linux-gnu")
    os.umask(0o077)
    SOCKET.mkdir(parents=True, exist_ok=True)
    password = secrets.token_hex(32)
    pwfile = RUNTIME / "init-password"
    pwfile.write_text(password)
    try:
        run(
            BIN / "initdb",
            "-D",
            DATA,
            "-L",
            SHARE,
            "-U",
            "brain_admin",
            "--pwfile",
            pwfile,
            "--auth-local=peer",
            "--auth-host=scram-sha-256",
            "--encoding=UTF8",
            "--locale=C.UTF-8",
        )
    finally:
        pwfile.unlink(missing_ok=True)
    with (DATA / "postgresql.conf").open("a") as config:
        config.write(
            f"\nlisten_addresses = '127.0.0.1'\nport = 55432\n"
            f"unix_socket_directories = '{SOCKET}'\n"
            f"dynamic_library_path = '{LIB}'\n"
        )
    # Debian builds use a compiled-in $libdir; relocate only our private files.
    control = SHARE / "extension/vector.control"
    control.write_text(control.read_text().replace("$libdir/vector", str(LIB / "vector")))
    (ROOT / ".env").write_text(
        "APP_ENV=development\nLOG_LEVEL=INFO\nTELEGRAM_BOT_TOKEN=\n"
        f"DATABASE_URL=postgresql+asyncpg://ai_brain:{password}@127.0.0.1:55432/ai_brain\n"
    )
    (RUNTIME / "admin-password").write_text(password)
    run(BIN / "pg_ctl", "-D", DATA, "-l", ROOT / "logs/postgres.log", "start", "-w")
    print("Private cluster ready; provision ai_brain using the saved private admin password.")


if __name__ == "__main__":
    main()
