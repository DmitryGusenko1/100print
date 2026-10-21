from fastapi import FastAPI
from sqlalchemy import text

from app.database.session import engine

app = FastAPI(title="AI Business Brain", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
