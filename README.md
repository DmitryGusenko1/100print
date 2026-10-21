# Единая память AI-помощников

Первый рабочий контур: Telegram-бот + PostgreSQL + HTTP API общей памяти.

## Что хранится
- владельцы;
- проекты;
- диалоги;
- сообщения;
- решения;
- задачи;
- версии краткого состояния проекта.

## Важное ограничение
Обычные чаты ChatGPT и отдельные сессии Codex автоматически сюда не попадают. Telegram сохраняет только сообщения, обработанные этим ботом. Интеграция ChatGPT/Codex через отдельный инструмент или MCP — следующий этап.

## Требования
- Python 3.11+;
- PostgreSQL;
- systemd;
- без Docker.

## Настройка
1. Создать PostgreSQL пользователя и базу.
2. Скопировать `.env.example` в приватный env-файл вне Git.
3. Заполнить:
   - `DATABASE_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `ALLOWED_TELEGRAM_IDS`
   - `API_KEY`
   - `AI_API_KEY`
   - при необходимости `AI_BASE_URL` и `AI_MODEL`.
4. Установить приложение:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -e .
   ```
5. Применить миграции:
   ```bash
   .venv/bin/alembic upgrade head
   ```
6. Проверить API:
   ```bash
   .venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8088
   ```
   затем `GET /health`.
7. Только после проверки, что нет другого polling-процесса с тем же Telegram-токеном, запускать:
   ```bash
   .venv/bin/python -m app.bot
   ```

## Telegram-команды
- `/start` — инициализация владельца и проекта;
- `/projects` — список проектов;
- `/project <UUID>` — переключение активного проекта;
- `/status` — текущий статус и активный проект.

## Надёжность
Входящее Telegram-сообщение сохраняется до вызова AI. Если AI недоступен, сообщение остаётся в базе. Повторная доставка того же сообщения не создаёт дубль благодаря уникальности `source + external_id`.

## API
API требует два заголовка:
- `X-API-Key`
- `X-Owner-Telegram-Id`

Доступ к проекту проверяется на каждом запросе. API на VPS по умолчанию должен слушать только `127.0.0.1`. Внешний доступ — только через HTTPS reverse proxy.

Основные endpoints:
- `POST /messages`
- `GET /projects/{project_id}/context`
- `GET /projects/{project_id}/tasks`
- `POST /tasks`
- `PATCH /tasks/{task_id}`
- `POST /decisions`
- `POST /states`
- `GET /health`

## Поиск контекста
Используется PostgreSQL full-text search плюс последние сообщения, текущее состояние, задачи и решения. Векторный поиск пока не нужен.

## Резервное копирование
`scripts/backup.sh` создаёт custom-format dump PostgreSQL. Проверять восстановление нужно на отдельной тестовой базе через `scripts/restore_test.sh`.

Копия на том же VPS не защищает от полной потери VPS, поэтому рабочие backup-файлы нужно дополнительно выносить на другой хост/хранилище.

## systemd
Подготовлены:
- `deploy/ai-memory-api.service`
- `deploy/ai-memory-bot.service`

Перед установкой на VPS обязательно проверить существующие порты, пользователей, systemd services и процессы Telegram polling. Ничего существующее заменять или останавливать без отдельного решения нельзя.
