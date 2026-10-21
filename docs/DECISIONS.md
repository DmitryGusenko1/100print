# DECISIONS

## ADR-001 — PostgreSQL + pgvector
Статус: принято.

Долговременная память и структурированные бизнес-сущности хранятся в PostgreSQL. Семантический поиск — pgvector.

## ADR-002 — Telegram-first
Статус: принято.

Основной интерфейс MVP — один Telegram-бот. Несколько ботов могут появиться позже как дополнительные точки входа, но ядро остаётся единым.

## ADR-003 — AI Organization
Статус: принято.

Используем иерархию CEO/Chief of Staff -> Department Heads -> Specialist Agents -> Skills.

## ADR-004 — LLM abstraction
Статус: принято.

Агенты используют BrainProvider. Конкретный LLM/CLI не является частью доменной модели.

## ADR-005 — Markdown is projection, DB is source of truth
Статус: принято.

Obsidian/Markdown используется как удобный человекочитаемый слой и экспорт. Главный источник истины — серверная БД.
