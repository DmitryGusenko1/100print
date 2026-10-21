import asyncio

from sqlalchemy import text

from app.database.session import engine


async def main() -> None:
    async with engine.connect() as connection:
        value = await connection.scalar(text("SELECT 1"))
    if value != 1:
        raise SystemExit("database check failed")
    print("database: ok")


if __name__ == "__main__":
    asyncio.run(main())
