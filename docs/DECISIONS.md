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

## ADR-006 — Atomic Telegram ingestion
Статус: принято.

Первый vertical slice сохраняет Telegram message и создаёт memory_item типа thought в одной транзакции. Исходный original_text не нормализуется и не перезаписывается. Повторная доставка Telegram update определяется по source + external_id.

## ADR-007 — Scope and private VPS deployment (2026-10-21)
The explicit execution boundary `/opt/ceo-orchestrator` overrides the issue's
`/opt/ai-business-brain` target. Use a separate main worktree at
`/opt/ceo-orchestrator/ai-business-brain` to preserve the existing orchestrator.
No foreign .env files are read. Without sudo, unpack Ubuntu PostgreSQL packages
inside `.runtime`, initialize a new cluster with SCRAM on localhost:55432 and
provision only its `ai_brain` database. API uses free port 18090. systemd units are
prepared/verified; installation and reboot persistence remain blocked by privileges
and the directory boundary. A dedicated Telegram token is still required.

## ADR-008 — Verified persistence contract (2026-10-21)
Use the existing asyncpg driver for Alembic; do not require an undeclared psycopg2.
Serialize Telegram ingestion per chat with transaction-scoped PostgreSQL advisory
locks, including the first conversation insert. Commit message and thought together;
redelivery returns the same IDs. A DB trigger rejects changes to original_text and
updates updated_at. Integration tests exercise real PostgreSQL; mocked Telegram
transport does not count as a live Telegram acceptance test. Freeze tested dependencies.

## ADR-009 — Safe test discovery and acceptance (2026-10-21)
Limit pytest discovery to `tests/` and protect the PostgreSQL runner with a main
guard. Collecting an executable `scripts/test_postgres.py` caused recursive pytest
subprocesses; the runner now explicitly targets `tests` even during broad collection.
Rechecked all 7 tests against the private ai_brain database, including transactional
ingestion and ACK. Restarted the existing private cluster and API after finding them
stopped. This is process startup only, not proof of systemd or reboot persistence.
Keep issue #1 open until dedicated Telegram credentials and privileged service
installation are available. No foreign credentials or services may be used as a workaround.
