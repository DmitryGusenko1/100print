# Hermes с существующим OAuth в изолированном rootfs

Установщик `ops/hermes/install.py` использует существующий
`/var/lib/100print-isolation/rootfs`, UID `ceo-w2p-agent`, авторизацию Hermes
`openai-codex` и тот же management bot **@hundredprintbot**. Новый платный API key,
ручная смена токенов и `/codex-runtime auto` в старом gateway не нужны.
Старые CLI containment, Codex wrapper, `app.isolation`, DB triggers и очередь
исполнителя остаются заблокированными. Старый runtime/config не переключается.

## Что установлено кодом, а что проверяется только на VPS

В рабочей копии нет доступного установленного Hermes runtime и его OAuth secrets.
Адаптер изучен по закреплённому [исходнику Hermes
2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19](https://github.com/NousResearch/hermes-agent/tree/2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19):
`hermes_cli/auth.py`, `auth_codex.py`, `auth_constants.py`,
`agent/codex_headers.py`, `agent/transports/codex.py` и Responses adapter.
На VPS установщик проверяет фактически скопированный provider через AST и
сохраняет SHA256 его файлов в host receipt. Код старого проекта от root не
импортируется и не выполняется. Несовместимые store version, OAuth constants или
locking contract приводят к отказу; один лишь upstream reference не считается
проверкой установленной версии.

Локальные unittest используют синтетические JWT, временные файлы и mock upstream.
Они проверяют ротацию, concurrency, ограничения адаптера, очередь, отказ от
неопределённого replay, откат при ошибках этапов и повторную установку. Они **не
проверяют живую модель, systemd/rootfs на VPS или доставку Telegram**.

## Разделение процессов

| Компонент | UID / окружение | Возможности |
| --- | --- | --- |
| `100print-hermes-model.service` / `broker.py` | `ceoorch`, отдельный mount namespace с `RootDirectory` | Только OAuth refresh и запросы модели на фиксированные HTTPS endpoints. Канонический Hermes home доступен только этому доверенному процессу как `/oauth`; нет монтирования всего проекта, host `/proc` или host `/run`. |
| `100print-hermes-broker.service` / `transport.py` | отдельный `ceo-w2p-transport` | Только Telegram владельца, SQLite queue, выдача task grants и проверка model usage receipts. Нет OAuth secrets и исполнения команд. Имя старого API-key unit сохранено для обратимого обновления. |
| `100print-hermes-agent.service` / `runtime.py` | `ceo-w2p-agent`, существующий rootfs, private network | Hermes CLI, локальные terminal/file tools и их дочерние процессы. Запись в отдельный workspace; нет host home, OAuth, Telegram/DB/GitHub/SSH credentials или Docker socket. |

`broker.py` не импортирует Hermes и не запускает subprocess/CLI/app-server/tools.
Вызовы функций в Responses — только JSON. Допускаются только custom function
schemas; hosted shell/computer/web_search/MCP/file tools отвергаются. Инструменты
исполняет Hermes внутри worker rootfs. Дочерние процессы наследуют mount/network
namespace, UID, capability restrictions и cgroup. Старый containment не изменяется;
новый Hermes получает собственный конфиг только внутри изолированного workspace.

Worker видит два конкретных Unix socket каталога: модель и очередь. Peer UID
проверяется через `SO_PEERCRED`. Модель требует HMAC grant с task ID и сроком не
более 600 секунд, выданный доверенным транспортом; signing key агенту не выдаётся.
Ограничены attempts (12 на задачу, включая ошибки), размер wire/SSE (2 MB), контекст
(100 сообщений), время upstream и время CLI. Usage хранится отдельно от агента.
Worker не может доказать успешный inference собственным `ok` или `api_calls`.

Брокер принимает Chat Completions от локального SDK, переводит text/function
history в Codex Responses, а завершённый Responses stream обратно в completion.
При необходимости worker возвращает SDK-compatible SSE. Endpoint модели всегда
`https://chatgpt.com/backend-api/codex/responses`, `store=false`, `stream=true`.
Внешние URL, headers, model, previous_response_id и endpoint от агента не
принимаются. Native hosted tools не включаются. Account/residency headers берутся
из OAuth JWT. Это адаптер подписки ChatGPT; API-key fallback отсутствует.

HTTPS использует фиксированные hostname/path, проверку сертификата и hostname,
без environment proxy и редиректов. Каждый DNS результат проверяется на публичный
IP; соединение открывается по проверенному IP с исходным TLS SNI, без повторного
DNS. Приватные/loopback/link-local IPv4/IPv6 отвергаются. Дополнительно systemd
cgroup IPAddressDeny проверяется реальным `BPF_PROG_QUERY` для ingress/egress.
Нельзя молча продолжить без filters. `bpftool` и установка пакетов не нужны.

## OAuth и резервная копия

На хосте автоматически читаются только объявленные файлы одного проекта:

* `ai-team/runtime/hermes-home/auth.json`;
* `ai-team/runtime/hermes-home/.env` и `config.yaml`;
* `config/telegram.env`.

Токен и один личный owner ID должны совпадать в существующих Telegram configs.
Provider должен быть `openai-codex`. Инсталлятор не угадывает ID, не заменяет токен,
не создаёт новую OAuth login session и не просит вводить новый API key.
Настройки доверенных служб записываются root-owned, 0600, и передаются через
systemd LoadCredential. Telegram config и model config разделены. Секреты не
печатаются и не попадают в GitHub или агентский runtime.

**OAuth не клонируется в независимое хранилище.** Канонический legacy `auth.json`
остаётся единственным источником. Брокер использует тот же `auth.lock` / flock,
что Hermes, перечитывает token pair под lock, обновляет через фиксированный
`https://auth.openai.com/oauth/token` и атомарно сохраняет свежую пару с fsync и
mode 0600. Обновляются singleton и его native credential-pool aliases, независимые
аккаунты/другие providers сохраняются. Ротация не меняет principal.

Перед HTTP refresh сохраняется durable intent с hash поколения, без самих токенов.
Потеря ответа/неопределённый 5xx не вызывает blind retry single-use refresh token.
После crash между успешной записью новой пары и удалением intent поколение
сверяется: если новая пара уже сохранена, операция завершается безопасно. Два
одновременных refresh не расходуют одну пару дважды. Определённые OAuth 4xx/429
не считаются неизвестным исходом и не оставляют блокирующий intent.

Root-only backup содержит исходный auth.json, legacy .env/config, unit texts и
service states. **Откат никогда не записывает старый refresh token поверх свежего.**
Резервная копия OAuth служит для диагностики, а не автоматического replay.
Старый runtime после обычного отката использует актуальный канонический store.
Если результат refresh действительно неизвестен и новая пара не была сохранена,
обе стороны polling остаются остановленными, snapshot сохраняется, статус
`FAILED_CLOSED_OAUTH_REFRESH_OUTCOME_UNKNOWN`. Восстановить неизвестный ответ
удалённого OAuth server локальным откатом невозможно; слепое восстановление backup
могло бы отозвать всю token family. Containment при этом остаётся на месте.

## Этапы установки на VPS

Нужны существующий baseline, systemd с cgroup v2/BPF, host `/usr/bin/python3`,
util-linux (`nsenter`, `setpriv`, `runuser`), рабочий публичный DNS и доступ к
Telegram/ChatGPT/auth endpoints. Архитектуры BPF query: x86_64, aarch64, riscv64.
Пакеты и общесерверные настройки автоматически не меняются.

Если `hermes-runtime` отсутствует, копируются Python dependencies существующего
Hermes venv и единственный editable source внутри его runtime. Экспорт не запускает
legacy code. Удаляются `.env`, OAuth, history, secrets, `.pth`, metadata с source
URLs и cache. Source symlinks/special files не следуются; uv hardlinks собственного
владельца копируются в новые независимые файлы. Итоговое дерево root-owned,
неизменяемо для агента, без symlinks/hardlinks. Несовместимый Python ABI, неизвестный
editable source или неожиданные ссылки приводят к раннему отказу. Уже существующий
курированный runtime проверяется по ownership и типам каждого файла.

1. Проверить provider/store, согласованность Telegram owner, baseline unit и его
   настоящий Result/ExecMainStatus; сохранить backup/snapshot до замены служб.
2. Установить versioned root-owned код/конфиги, выполнить systemd-analyze verify,
   запустить модельный брокер и доверенный транспорт **без polling**. Транспорт
   проверяет getMe=`hundredprintbot`, отсутствие webhook. Проверить cgroup filters.
3. Запустить worker; `probe.py` выполняется как ExecStartPre под его ограничениями,
   затем повторяется через nsenter в namespace настоящего worker со сбросом
   UID/GID/supplementary groups. Проверяются host/private paths, read-only policy,
   writable workspace, symlink/hardlink escape, private/metadata IPv4/IPv6, дочерний
   процесс и наследование запрета private network.
4. Остановить старый Telegram gateway и подтвердить inactive. Проверить system
   legacy bot и оставшиеся poller processes этого проекта. **Новый polling ещё
   выключен.** Старый runtime mode/config и containment не меняются.
5. Настоящий Hermes CLI должен через OAuth-брокер вызвать модель, своим локальным
   инструментом создать файл с непредсказуемым nonce, проверить отказ host paths и
   закончить ответом `ISOLATED_HERMES_OK`. Нужны минимум два успешных model calls,
   подтверждённые брокером. Файл и nonce дополнительно проверяются независимо в
   namespace worker; root не читает агентские symlinks на host filesystem.
6. Повторно убедиться в отсутствии старого получателя, включить новый polling.
   Консоль выдаст `/hermes Проверка изолированного Hermes <nonce>`. Владелец
   отправляет её в **@hundredprintbot**. За 300 секунд нужны свежий inbound ровно
   владельца в private chat, model completion и успешный Telegram sendMessage для
   этого конкретного nonce. Старое подтверждение или произвольный ответ не подходит.
7. Только после приёмки отключить автозапуск старого **транспорта** и включить новые
   службы. Старый executor/очередь/DB/CLI containment не разблокируется.

Повторный запуск — новая проверяемая транзакция, без второго poller. flock
сериализует установку и откат. При ошибке проверки, таймауте, SIGTERM/HUP или
KeyboardInterrupt новые процессы останавливаются и подтверждается их остановка
**до** восстановления старого транспорта/active/enabled states. При Telegram 409
транспорт завершается с кодом 78 без автоматического restart в конфликтующий
polling. Нельзя объявить READY при отсутствующем E2E или незавершённом откате.

Инсталлятор управляет известными локальными units и pollers этого проекта. Он не
может доказать отсутствие неизвестного потребителя токена на другом сервере.
409/ошибка доставки не считается успехом и не разрешает включить старый и новый
локальные transport одновременно.

Итоговый host receipt: `HOST_HERMES_OAUTH_TELEGRAM_VERIFIED_LEGACY_EXECUTION_PAUSED`.
Во время установки: `INSTALLING_NOT_READY`; обычный откат:
`ROLLED_BACK_NOT_NEW_HERMES_READY`. В receipt нет токенов, owner ID, prompt/ответов.

## Запуск и восстановление

Из проверенного закреплённого checkout достаточно:

```sh
sudo python3 ops/hermes/install.py
```

Не надо вручную менять runtime или токены. Во время установки понадобится только
отправить выданную проверочную команду боту. Установщик не запускался на VPS из
рабочей песочницы; успешного host receipt в репозитории нет.

После SIGKILL/отключения питания незавершённый snapshot блокирует новую установку:

```sh
sudo python3 ops/hermes/install.py --rollback
```

После успеха тот же параметр откатывает последнюю установку. Versioned code,
workspace, identities и backup сохраняются; чужие файлы не удаляются. Очередь не
переигрывает interrupted inference. Telegram отправляется at-most-once attempt:
неопределённый результат POST не вызывает повторную отправку. Старые состояния
очереди и актуальная OAuth rotation не заменяются устаревшим backup.

## Локальные проверки

```sh
.venv/bin/python -m unittest discover -s tests -p test_hermes_installer.py
.venv/bin/python -m unittest discover -s tests -p test_isolation.py
python3 ops/isolation/install-isolated-runtime.py --self-test
```

Fault-injection тесты временно симулируют host stages, включая успех/повторную
установку. Их временные receipts не являются свидетельством VPS-проверки.
Старый `test_hermes_bridge.py` требует реальную проектную PostgreSQL и секрет;
он не входит в локальную проверку этого установщика.
