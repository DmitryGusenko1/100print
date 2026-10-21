from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Conversation, MemoryItem, Message


@dataclass(frozen=True)
class IngestResult:
    message_id: str
    memory_id: str
    duplicate: bool = False


async def ingest_telegram_text(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int,
    telegram_message_id: int,
    text: str,
) -> IngestResult:
    async with session.begin():
        # Serialize a chat inside PostgreSQL, including concurrent first messages.
        await session.execute(
            sql_text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"telegram:{chat_id}"},
        )
        conversation_external_id = str(chat_id)
        message_external_id = f"{chat_id}:{telegram_message_id}"

        existing = await session.scalar(
            select(Message).where(
                Message.source == "telegram",
                Message.external_id == message_external_id,
            )
        )
        if existing:
            memory = await session.scalar(
                select(MemoryItem).where(MemoryItem.source_message_id == existing.id)
            )
            return IngestResult(
                message_id=str(existing.id),
                memory_id=str(memory.id) if memory else "",
                duplicate=True,
            )

        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.source == "telegram",
                Conversation.external_id == conversation_external_id,
            )
        )
        if conversation is None:
            conversation = Conversation(
                source="telegram",
                external_id=conversation_external_id,
            )
            session.add(conversation)
            await session.flush()

        message = Message(
            conversation_id=conversation.id,
            project_id=conversation.project_id,
            source="telegram",
            external_id=message_external_id,
            sender_id=str(user_id),
            role="user",
            text=text,
        )
        session.add(message)
        await session.flush()

        memory = MemoryItem(
            project_id=conversation.project_id,
            source="telegram",
            source_message_id=message.id,
            type="thought",
            original_text=text,
            normalized_text=text.strip(),
            importance=0.5,
            status="active",
            metadata_={
                "telegram_chat_id": chat_id,
                "telegram_user_id": user_id,
                "telegram_message_id": telegram_message_id,
            },
        )
        session.add(memory)

        await session.flush()
        result = IngestResult(message_id=str(message.id), memory_id=str(memory.id))
    return result
