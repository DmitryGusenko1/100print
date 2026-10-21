"""Integration tests use only explicitly supplied AI Brain database credentials."""

import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.models import Conversation, MemoryItem, Message
from app.services.ingestion import ingest_telegram_text

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to a migrated AI Brain DB"
)


@pytest_asyncio.fixture
async def store():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    chat = -(uuid.uuid4().int % (2**62))
    yield factory, chat
    async with factory.begin() as session:
        conversations = select(Conversation.id).where(Conversation.external_id == str(chat))
        messages = select(Message.id).where(Message.conversation_id.in_(conversations))
        await session.execute(delete(MemoryItem).where(MemoryItem.source_message_id.in_(messages)))
        await session.execute(delete(Conversation).where(Conversation.external_id == str(chat)))
    await engine.dispose()


async def ingest(factory, chat, message_id=1, content="  Важная мысль  "):
    async with factory() as session:
        return await ingest_telegram_text(
            session, chat_id=chat, user_id=123, telegram_message_id=message_id, text=content
        )


async def test_text_is_persisted_and_retry_is_idempotent(store):
    factory, chat = store
    first = await ingest(factory, chat)
    retry = await ingest(factory, chat)
    assert first.message_id == retry.message_id
    assert first.memory_id == retry.memory_id
    assert retry.duplicate
    async with factory() as session:
        memory = await session.get(MemoryItem, uuid.UUID(first.memory_id))
        assert memory.original_text == "  Важная мысль  "
        assert memory.normalized_text == "Важная мысль"
        assert memory.type == "thought"
        assert memory.source_message_id == uuid.UUID(first.message_id)


async def test_concurrent_first_messages_and_duplicate_delivery(store):
    factory, chat = store
    results = await asyncio.gather(*(ingest(factory, chat, i % 3) for i in range(9)))
    assert len({result.message_id for result in results}) == 3
    assert len({result.memory_id for result in results}) == 3
    async with factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.external_id == str(chat))
        )
        assert count == 1


async def test_original_text_cannot_be_overwritten(store):
    factory, chat = store
    result = await ingest(factory, chat)
    async with factory() as session:
        with pytest.raises(DBAPIError, match="original_text is immutable"):
            await session.execute(
                text("UPDATE memory_items SET original_text=:content WHERE id=:id"),
                {"content": "changed", "id": uuid.UUID(result.memory_id)},
            )
        await session.rollback()
        memory = await session.get(MemoryItem, uuid.UUID(result.memory_id))
        assert memory.original_text == "  Важная мысль  "


async def test_failure_rolls_back_both_message_and_conversation(store):
    factory, chat = store
    with pytest.raises(DBAPIError):
        # sender_id is varchar(255); fail after the conversation is flushed.
        async with factory() as session:
            await ingest_telegram_text(
                session, chat_id=chat, user_id="x" * 256, telegram_message_id=1, text="failure"
            )
    async with factory() as session:
        assert (
            await session.scalar(select(Conversation).where(Conversation.external_id == str(chat)))
            is None
        )


async def test_bot_ack_contains_committed_ids(store, monkeypatch):
    from app.bot import main as bot

    factory, chat = store
    monkeypatch.setattr(bot, "SessionLocal", factory)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=123),
        chat=SimpleNamespace(id=chat),
        message_id=1,
        text="telegram handler smoke",
        answer=AsyncMock(),
    )
    await bot.handle_text(message)
    ack = message.answer.await_args.args[0]
    parts = dict(part.split("=", 1) for part in ack.split()[1:])
    async with factory() as session:
        assert await session.get(Message, uuid.UUID(parts["message_id"]))
        assert await session.get(MemoryItem, uuid.UUID(parts["memory_id"]))
