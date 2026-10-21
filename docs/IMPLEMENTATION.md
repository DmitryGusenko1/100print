# IMPLEMENTATION

## Цель этого файла

Это рабочая инструкция для Codex. Реализацию вести по этапам ниже. После каждого законченного этапа:
1. запустить тесты;
2. обновить `docs/TASKS.md`;
3. зафиксировать архитектурные решения в `docs/DECISIONS.md`;
4. сделать атомарный commit.

## Этап 0 — базовая инфраструктура

- Python 3.12+
- отдельный venv
- PostgreSQL
- pgvector
- systemd
- конфигурация через .env
- structured logging
- health endpoint

Критерий готовности:
- приложение стартует;
- health возвращает OK;
- подключение к БД проходит.

## Этап 1 — Telegram MVP

Реализовать:
- aiogram bot;
- обработку text;
- обработку voice как сохраняемый input;
- сохранение оригинального Telegram message_id;
- единый InputEnvelope;
- простой ответ пользователю.

InputEnvelope:
```json
{
  "user_id": "",
  "chat_id": "",
  "message_id": "",
  "source": "telegram",
  "content_type": "text|voice|document",
  "text": "",
  "file_id": null,
  "created_at": ""
}
```

Критерий:
- сообщение Telegram попадает в БД и получает ID.

## Этап 2 — память

Таблицы:
- projects
- conversations
- messages
- memory_items
- memory_links
- decisions
- tasks
- agents
- departments
- department_members
- council_sessions
- council_messages
- skill_registry

Для `memory_items` предусмотреть:
- original_text
- normalized_text
- summary
- type
- project_id
- importance
- metadata JSONB
- embedding vector
- created_at
- updated_at

Критерий:
- можно сохранить мысль;
- можно найти её по тексту;
- можно получить историю.

## Этап 3 — Router

Создать `IntentRouter` и `DepartmentRouter`.

Intent:
- save_idea
- ask_question
- analyze
- create_plan
- find_memory
- make_decision
- assign_task

Department:
- strategy
- marketing
- seo
- sales
- finance
- operations
- general

Complexity:
- L1 single agent
- L2 department
- L3 multi-department
- L4 full council

## Этап 4 — AI Organization

Сущности:
- Organization
- Department
- DepartmentHead
- Agent
- Skill
- Task
- Handoff

Каждый DepartmentHead обязан уметь:
1. принять задачу;
2. декомпозировать;
3. назначить сотрудников;
4. запросить контекст из памяти;
5. сделать handoff другому подразделению;
6. получить ответ;
7. выявить конфликт;
8. инициировать согласование;
9. вернуть структурированный departmental_result.

departmental_result:
```json
{
  "department": "",
  "conclusion": "",
  "arguments": [],
  "risks": [],
  "assumptions": [],
  "requested_handoffs": [],
  "recommended_actions": [],
  "confidence": 0.0
}
```

## Этап 5 — Cross-Department Council

Алгоритм:

### Round 0
Chief of Staff формулирует problem / goal / constraints / decision criteria.

### Round 1
Руководители дают независимые позиции.

### Round 2
Каждый получает позиции остальных и обязан:
- поддержать минимум один тезис;
- оспорить минимум один тезис;
- назвать упущенный фактор;
- при необходимости изменить позицию.

### Round 3
Moderator строит карту:
- agreements
- disagreements
- unknowns
- blockers

### Round 4
Точечные вопросы отправляются только релевантным подразделениям.

### Round 5
Critic атакует почти готовое решение.

### Round 6
Chief of Staff формирует:
- decision
- why
- rejected alternatives
- risks
- assumptions
- action plan
- KPI
- next decision point

Все раунды сохраняются.

## Этап 6 — Context Builder / Retrieval

ContextPackage:
```text
CURRENT_MESSAGE
CURRENT_PROJECT
PROJECT_GOALS
RECENT_CONTEXT
RELEVANT_MEMORIES
PREVIOUS_DECISIONS
OPEN_TASKS
KNOWN_CONSTRAINTS
RELATED_DOCUMENTS
UNRESOLVED_CONTRADICTIONS
```

Поиск:
1. full text candidates;
2. vector candidates;
3. metadata filters;
4. merge + rerank;
5. LLM relation verification;
6. создание memory_links.

## Этап 7 — голос

- скачать Telegram voice;
- сохранить оригинал;
- транскрибировать через отдельный SpeechProvider;
- исходный файл не удалять;
- транскрипцию сохранять как отдельное поле;
- дальше обрабатывать как text.

## Этап 8 — Markdown / Obsidian слой

База данных остаётся источником истины.

Создать экспорт/синхронизацию в Markdown:
```text
vault/
  projects/
  ideas/
  decisions/
  meetings/
  departments/
  daily/
```

Каждый Markdown-файл должен содержать стабильный database ID в frontmatter.

## Этап 9 — наблюдаемость

Нужны:
- app logs;
- audit trail;
- agent execution logs;
- token/cost accounting;
- duration;
- failure reason;
- retry state.

## Запреты

- не хранить память только в prompt;
- не привязывать бизнес-логику к одному LLM;
- не позволять агентам бесконечно спорить;
- не терять исходный пользовательский текст;
- не изменять исходные мысли задним числом;
- не давать агентам самостоятельно выполнять опасные внешние действия без отдельной policy.

## Порядок разработки прямо сейчас

1. Создать структуру приложения.
2. Поднять config + logging.
3. Добавить FastAPI /health.
4. Добавить PostgreSQL модели и Alembic.
5. Добавить Telegram text ingestion.
6. Протестировать end-to-end: Telegram -> DB -> ACK.
7. После этого переходить к Router и AI-агентам.
