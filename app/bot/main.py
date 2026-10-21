import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message as TelegramMessage

from app.config import settings
from app.database.session import SessionLocal
from app.services.ingestion import ingest_telegram_text

router = Router()
log = logging.getLogger(__name__)


@router.message(F.text)
async def handle_text(message: TelegramMessage) -> None:
    if message.from_user is None or message.text is None:
        return

    async with SessionLocal() as session:
        result = await ingest_telegram_text(
            session,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            telegram_message_id=message.message_id,
            text=message.text,
        )

    await message.answer(
        f"ACK message_id={result.message_id} memory_id={result.memory_id}"
    )


async def run() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    logging.basicConfig(level=settings.log_level)
    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
