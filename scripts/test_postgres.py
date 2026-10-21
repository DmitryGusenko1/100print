"""Run tests against this application's configured, migrated PostgreSQL database."""

import os
import subprocess
import sys

from app.config import settings


def main() -> int:
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        env={**os.environ, "TEST_DATABASE_URL": settings.database_url},
    )


if __name__ == "__main__":
    raise SystemExit(main())
