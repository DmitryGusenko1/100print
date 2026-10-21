import asyncio
from datetime import datetime, timezone

async def heartbeat():
    while True:
        now = datetime.now(timezone.utc).isoformat()
        with open("/opt/ceo-orchestrator/logs/heartbeat.log", "a") as f:
            f.write(f"{now} CEO Orchestrator alive\n")
        await asyncio.sleep(60)

async def main():
    await heartbeat()

if __name__ == "__main__":
    asyncio.run(main())
