"""Provision only the dedicated ai_brain database in our private cluster."""

import asyncio
from pathlib import Path

import asyncpg


async def main():
    root = Path(__file__).resolve().parents[1]
    password = (root / ".runtime/admin-password").read_text()
    connection = await asyncpg.connect(
        user="brain_admin", password=password, host="127.0.0.1", port=55432, database="postgres"
    )
    try:
        # Generated hex only; never interpolate user-controlled identifiers or secrets.
        assert len(password) == 64 and all(c in "0123456789abcdef" for c in password)
        await connection.execute(f"CREATE ROLE ai_brain LOGIN PASSWORD '{password}'")
        await connection.execute("CREATE DATABASE ai_brain OWNER ai_brain")
    finally:
        await connection.close()
    connection = await asyncpg.connect(
        user="brain_admin", password=password, host="127.0.0.1", port=55432, database="ai_brain"
    )
    try:
        await connection.execute("CREATE EXTENSION vector")
    finally:
        await connection.close()
    print("ai_brain role, database and vector extension ready")


if __name__ == "__main__":
    asyncio.run(main())
