# Подключение 100print

## Уже реализовано

Локальный API: `http://127.0.0.1:8096`, MCP Streamable HTTP: `/mcp/`.
Все запросы, включая OpenAPI и health, требуют `Authorization: Bearer <token>`.
Секрет создан в `config/chatgpt.env` (0600, gitignored); не копируйте его в issue,
чат или Project Instructions. Общая БД — только `ceo_orchestrator`.

API запускает и перезапускает существующий `ceo-orchestrator`, если задан
CEO_CHATGPT_TOKEN. Новая systemd unit не обязательна. Шаблон отдельного сервиса
`config/systemd/ceo-chatgpt-api.service` — альтернативный способ; одновременно
оба способа на одном порту не запускайте: для отдельной unit задайте
CEO_CHATGPT_MANAGED=0 в config/chatgpt.env и перезапустите ceo-orchestrator.

## Минимальные действия владельца ChatGPT

1. Предоставить HTTPS URL с доверенным сертификатом или настроить поддерживаемый
   Secure MCP Tunnel до локального `/mcp/`. Не публиковать PostgreSQL. При reverse
   proxy задать точный внешний host в CEO_CHATGPT_ALLOWED_HOSTS в config/chatgpt.env.
   Изменение proxy/DNS за пределами этого репозитория здесь не выполняется.
2. Подключить endpoint как пользовательское приложение/MCP в доступном аккаунту
   режиме разработчика. Возможности зависят от плана и разрешений workspace.
   Этот сервер использует Bearer token, не реализует OAuth authorization server.
   Если UI не поддерживает передачу Bearer credentials, нужен совместимый
   авторизованный gateway (OAuth → приватный Bearer backend) или HTTPS API adapter
   с серверным секретом. Не выбирайте публичный анонимный доступ ради подключения.
3. Сделать инструмент доступным в проекте «100 ТИПОГРАФИЙ» и вставить содержимое
   CHATGPT_PROJECT_INSTRUCTIONS.md в инструкции. Если текущий UI не позволяет
   инструменты внутри Projects, использование именно в Project пока заблокировано
   платформой; API-адаптер может использовать тот же контракт вне интерфейса Project.
4. Проверить: создать чат, записать решение с уникальной фразой, открыть второй
   чат и запросить эту фразу; создать задачу и дождаться get_task_result.

Документация OpenAI:
[Подключение MCP](https://developers.openai.com/api/docs/guides/custom-mcp-server),
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
Инструмент не получает скрытых системных событий ChatGPT автоматически: вызовы
выполняются моделью по инструкциям. Подключение в аккаунте требует владельца.

## HTTP fallback и контракт

`POST /tools/{method}`: JSON, project_id только `100print`; дополнительные поля запрещены.
MCP tools имеют те же имена и принимают объект `input` с этими полями.

| method | Обязательные поля |
| --- | --- |
| create_or_resume_conversation | external_session_id; source=chatgpt/telegram |
| append_message | conversation_id, text, request_id; role=user/assistant; kind=message по умолчанию |
| get_relevant_context | conversation_id, query; max_chars=2000..32000 |
| create_analysis_task | conversation_id, text, request_id |
| get_task_status / get_task_result | task_id |
| append_decision / append_action_item | conversation_id, text, request_id |
| search_memory | query; limit=1..50 |

request_id обязателен на записи, стабилен при повторе. Повтор с другим текстом
отклоняется. Сессии разделены по source/external_session_id. UUID чужой/обычной
задачи очереди не позволяет прочитать её через проектный API. Один токен имеет
доступ ко всему проекту; это не многопользовательская система ACL.

Контекст ограничен размером и содержит traceable записи, текущие сообщения,
решения/факты/результаты, открытые вопросы/противоречия, ограничения и активные задачи.
Ранжирование: full-text + importance + confidence + recency. Для retrieval
резервируется отдельная доля контекста, чтобы открытые вопросы не вытесняли решения.
Длинные тексты возвращаются фрагментами с text_truncated=true; полная запись остаётся в БД. Семантический индекс
использует ограниченный русско-английский словарь бизнес-понятий; это не neural
embedding retrieval, и произвольные перефразировки могут не находиться.

## Telegram

`app.telegram_memory.receive` и `record_reply` используют ту же память, retrieval и
очередь, что ChatGPT. Адаптер `app.telegram_bot` запускается при наличии
CEO_TELEGRAM_TOKEN и CEO_TELEGRAM_ALLOWED_CHATS. Не запускайте два polling-процесса
для одного bot token. Старый ai-business-brain ACK bot использует отдельную БД;
его нужно остановить перед переключением токена на новый адаптер. Исторические
записи его БД автоматически не мигрируются. В этой задаче старый bot не меняется.

## Production AI

По умолчанию CEO_BRAIN_MODE=deterministic: маршрутизация/Council работают, но ответы
демонстрационные, confidence=0. Для реальных консультаций нужен настроенный
production BrainProvider из #5; его контракт дополнен ANALYTICAL. Сбой production
не заменяется демонстрационным ответом. API не требует OpenAI API key для памяти.

## Проверка

```
.venv/bin/python -m unittest tests.test_chatgpt tests.test_organization -v
.venv/bin/python -m unittest tests.test_chatgpt_restart tests.test_runtime tests.test_organization_postgres -v
```

Тесты используют только ceo_orchestrator и оставляют маркированные тестовые записи
для аудита. Не запускайте live suite на сервере во время важного анализа.
