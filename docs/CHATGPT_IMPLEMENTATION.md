# Issue #6 — реализация и границы готовности

Серверная часть: 9 HTTP/MCP tools; постоянные conversations/messages; типизированная
память с provenance/confidence/importance; полнотекстовый и ограниченный концептный
поиск; bounded Context Package; автоматические L1/L2/L3/L4; Critic и structured
Analytical Protocol; очередь с checkpoint recovery; отдельный Telegram transport,
использующий ceo_orchestrator. Записи ответа ChatGPT выполняются инструментом до
отправки пользователю, согласно Project Instructions.

Миграция добавляет только project_* таблицы в ceo_orchestrator. Исходные данные и
старые таблицы не удаляются. Существующие неопубликованные файлы ai-business-brain,
app/github_watcher.py и app/github_worker.py не включены в коммит этой задачи.
Чужие env, БД и systemd units не изменялись. Никакие новые внешние сообщения через
Telegram в ходе проверки не отправлялись.

## Проверки

- tests.test_chatgpt: HTTP auth/project scope/input bounds, session resume,
  messages/assistant replies, idempotency, retrieval из нового чата, bounded context,
  концептный поиск «скидка» → pricing, двусторонняя общая память Telegram/ChatGPT,
  семь маршрутов (L1/L2 и пять бизнес-примеров issue), structured analysis,
  Finance/Marketing conflict, Critic, Council, MCP initialize/list/call.
- tests.test_chatgpt_restart: реальные SIGKILL и systemd recovery только собственного
  ceo-orchestrator, сохранность conversation/message/decision/pending task,
  обнаружение задачи в новом контексте, завершение анализа работающим worker и
  запись результатов/решений/action items/Council rounds в память.
- tests.test_organization: 12 существующих проверок контрактов/организации.
- tests.test_runtime и tests.test_organization_postgres: 7 существующих live
  проверок очереди, retry, crash recovery, каталога и восстановления checkpoints.
- pip check, compileall, git diff --check.

## Не подтверждено в production

Нет подключённой сессии владельца ChatGPT; HTTPS/tunnel и OAuth gateway не настроены.
MCP принимает Bearer token; поддержка этого способа авторизации в конкретном
ChatGPT UI должна проверяться владельцем. Нет настроенного production brain:
результаты deterministic явно демонстрационные. Нет токена/allowlist для запуска
нового Telegram polling transport; проверен адаптер и единая БД, а не live bot.
Существующий ai-business-brain ACK bot и его историческая БД не переключались и
не мигрировались. Автоматический перехват событий ChatGPT Projects платформа может
не предоставлять; инструкции модели не дают технической гарантии каждого вызова.

Поэтому серверный deliverable готов к подключению, но end-to-end пользовательский
сценарий в реальном ChatGPT Project пока нельзя честно объявить подтверждённым.
Оставшиеся действия описаны в CHATGPT_TOOL_SETUP.md.

Итог проверки на VPS: 17 тестов ChatGPT/organization — PASS (38.328 s);
9 live-проверок (включая один повтор retrieval) — PASS (85.301 s);
повтор crash/restart на окончательном коде — PASS (15.961 s).
Итого 25 уникальных тестов. pip check и git diff --check — PASS.
Локальный authenticated health возвращает status=ok, project_id=100print,
brain_mode=deterministic. Внешний end-to-end тест не выполнялся.
