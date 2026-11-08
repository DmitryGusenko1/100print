# Изолированный Hermes: установка и границы проверки

Новый контур использует существующий `/var/lib/100print-isolation/rootfs` и
`ceo-w2p-agent`. Старые CLI interlock, DB triggers, `app.isolation`, очередь и
Codex wrapper не разблокируются. Это подключение личного управления Hermes,
не разрешение производственных операций и не запуск прежней очереди.

## Авторизация модели — обязательная предпосылка

**Этот вариант поддерживает отдельный OpenAI API key для Chat Completions.
Перенос существующего Hermes OAuth / ChatGPT subscription не реализован.**
Нельзя считать старую OAuth-авторизацию совместимой или автоматически заменить
её платным API. До выбора владельцем этого способа подключения запускать
установку не следует. Если требуется сохранить OAuth, нужен другой адаптер брокера.

На хосте должен существовать `/etc/100print-hermes.json`, root:root, mode 0600:

```json
{
  "telegram_token": "ТОКЕН_СУЩЕСТВУЮЩЕГО_hundredprintbot",
  "owner": "ПОДТВЕРЖДЕННЫЙ_ЛИЧНЫЙ_TELEGRAM_USER_ID",
  "model_api_key": "ОТДЕЛЬНЫЙ_OPENAI_API_KEY",
  "model": "gpt-4.1-mini"
}
```

Значения не помещать в Git, аргументы команд, журнал или переписку.
Установщик намеренно не угадывает владельца и не читает общий `.env` проекта.
Наличие одного этого файла не доказывает работоспособность токенов.

## Устройство

* `100print-hermes-agent.service`: отдельный UID, RootDirectory, PrivateNetwork,
  сброшенные capabilities, NoNewPrivileges, read-only `/usr`, `/runtime`, код и
  ровно один брокерный каталог. Запись только в `hermes-workspace`; нет bind
  проекта, host /etc, /home, /proc, /run, SSH, Docker, DB или Telegram credentials.
  Локальный HTTP endpoint SDK существует только в собственной network namespace.
  Его порт не опубликован на хосте. Все дочерние процессы остаются в этом контуре.
* `100print-hermes-broker.service`: доверенный UID `ceo-w2p-transport`, секреты через
  systemd LoadCredential. Только фиксированные Telegram API методы и фиксированный
  `api.openai.com/v1/chat/completions`; без CONNECT, URL от агента, редиректов,
  произвольных заголовков или прокси из окружения. Текстовый контекст, модель из
  root-конфигурации, максимум 4096 output tokens / запрос и 12 model calls / задача.
  Приватные адреса ограничены cgroup IPAddressDeny; нужны systemd с cgroup BPF и
  рабочий публичный DNS. Для systemd-resolved используется upstream resolv.conf.
* Принимаются только `/hermes текст` от одного владельца в его личном чате.
  Группы, другой пользователь, другие команды и старые сообщения игнорируются.
  Ответ направляется только этому владельцу. Результат модели — недоверенный текст;
  в нём нет автоматически исполняемых действий брокера.
* SQLite хранит очередь и Telegram offset. Прерванные running-задачи становятся
  failed и не переигрываются. Отправка помечается перед POST: неопределённая доставка
  не вызывает повторную отправку. Это at-most-once попытка, не exactly-once доставка.
  Артефакты, prompts, ответы и очередь приватны и не публикуются в GitHub.

Межпроектный GitHub/DB/research broker сюда не входит: соответствующих credential,
методов и монтирований нет. Публичный web research и прежний Codex executor остаются
недоступны. Изолированный Hermes может использовать локальные инструменты внутри
rootfs; это не даёт ему права выполнять действия на хосте.

## Runtime и установка

Нужны уже установленный baseline, systemd, `/usr/bin/python3`, util-linux (`nsenter`,
`setpriv`, `runuser`), `bpftool` и доступ хоста к Telegram/OpenAI. Пакеты автоматически не
устанавливаются. Если `/var/lib/100print-isolation/hermes-runtime` отсутствует,
установщик **на хосте** копирует Python dependencies из существующего
`/opt/ceo-orchestrator/ai-team/runtime/hermes-venv` и единственный editable Hermes
source внутри того же runtime. В старый проект ничего не записывается, код оттуда
от root не запускается. `.env`, OAuth store, history, cron, `.pth`, secrets и
sessions не переносятся. Symlinks, special files, конфликты пакетов, несовпадение
Python ABI или неопределённый source останавливают установку. Не ослабляйте эту
проверку: подготовьте проверенное плоское дерево Python modules/dependencies,
root-owned, без links, secrets и writable-to-agent файлов в `hermes-runtime`.
Это дерево должно содержать `hermes_cli/main.py` и все зависимости для host Python.
Установщик не загружает и не обновляет сторонние dependencies.

Запуск из проверенной копии закреплённого коммита:

```sh
sudo python3 ops/hermes/install.py
```

Установщик сериализован flock. Он сохраняет unit files, active/enabled states и
переключатель в root-owned `hermes-rollback` до замены служб. На ошибке/таймауте
или SIGTERM/HUP/KeyboardInterrupt останавливает новые службы и восстанавливает
предыдущее состояние. При ошибке самого отката snapshot остаётся для повторения;
получить READY при этом нельзя. После SIGKILL/отключения питания:

```sh
sudo python3 ops/hermes/install.py --rollback
```

После успешной установки тот же параметр откатывает последнюю установку.
Изолированные workspace, диагностический runtime export, identity и release
каталоги сохраняются при откате; чужие файлы не удаляются. Незавершённая транзакция
блокирует новую установку до отката. Повторный запуск делает новую проверяемую
транзакцию, не создаёт второй gateway. Снимок последнего отката хранится в
`hermes-last-rollback.json`. Конфигурация broker credentials вне транзакции:
при её ручной смене оператор отвечает за совместимость с предыдущей версией.

## Проверки на хосте

1. Повторный запуск baseline и проверка systemd Result/ExecMainStatus.
2. systemd-analyze verify новых units; `bpftool` подтверждает прикреплённые
   ingress/egress filters в cgroup брокера (без них отказ); настоящий запуск брокера проверяет getMe
   (`hundredprintbot`) и отсутствие webhook, без getUpdates/sendMessage.
3. `probe.py` как ExecStartPre worker проверяет скрытые пути, read-only policy,
   рабочий каталог, symlink/hardlink escape, IPv4/private/metadata/IPv6 и дочерний
   процесс. Повторная проверка через nsenter использует namespace настоящего worker
   и сбрасывает UID/GID/supplementary groups. Это реальные проверки на хосте,
   а не моделирование systemd в локальном тесте.
4. Настоящий Hermes CLI через брокер: usage report с completed/API calls, успешный
   upstream model call, непустой ответ с `ISOLATED_HERMES_OK`. Никаких маркеров,
   подменяющих inference. Несовместимый CLI/config/protocol даёт отказ и откат.
5. Только после этого останавливается прежний user gateway. Если активен другой
   известный system Telegram consumer, переключение отклоняется. Новый брокер
   начинает polling. Консоль просит владельца отправить команду `/hermes ...`.
   В течение 300 секунд нужны настоящий inbound владельца, Hermes/model response
   и успешный Telegram sendMessage. Иначе откат с восстановлением старого gateway.
   Его startup interlock продолжает работать, старые executor/DB guards сохранены.
6. После приёмки старый gateway отключается от автозапуска, новые units включаются.
   При откате старое enabled state восстанавливается. Старый executor не включается.

Установщик проверяет два известных legacy consumers; он не доказывает отсутствие
неизвестного poller на другом сервере. Telegram 409/сетевой сбой приводит к
неполучению E2E и откату, а не к READY.

Итог на хосте: `hermes-evidence.json` со статусом
`HOST_HERMES_TELEGRAM_VERIFIED_LEGACY_EXECUTION_PAUSED`. Во время транзакции —
`INSTALLING_NOT_READY`, после отката — `ROLLED_BACK_NOT_NEW_HERMES_READY`.
Ни один локальный unittest не создаёт этот успешный host receipt.

## Локальная проверка

```sh
python3 -m unittest discover -s tests -p test_hermes_installer.py
.venv/bin/python -m unittest discover -s tests -p test_isolation.py
python3 ops/isolation/install-isolated-runtime.py --self-test
```

Эти тесты проверяют очередь, отказ поддельного успеха без model call, конфигурацию,
фиксированный upstream, фильтрацию владельца, неопределённую отправку, генерацию
units и откат на синтетических файлах. Они **не проверяют Telegram на сервере**.
Старый `test_hermes_bridge.py` требует реальную проектную PostgreSQL и секрет;
без них его результат нельзя объявлять успешным.

CLI/config сверены с [закреплённым исходником Hermes](https://github.com/NousResearch/hermes-agent/tree/2bd378ed1b8d6bf2192cb26e0a55ff3091e6bd19).
Фактическую совместимость установленного runtime проверяет только host inference.
