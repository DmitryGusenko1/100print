# 100print: установка изолированной базовой среды

Это реальная установка на VPS, а не marker согласования. Статус успешного результата: **HOST_BASELINE_READY_NOT_HERMES_READY**. Она НЕ включает Hermes, Codex, очередь или производство шаблонов.

## Одна команда администратора

Запустить на VPS обычным пользователем dmitry. Git fetch выполняется без sudo; текущая ветка, рабочие файлы и существующие сервисы не перезаписываются. Нужны git-доступ к origin и sudo для установки. Перед выполнением можно изучить закреплённый installer в репозитории.

```bash
bash -c 'set -euo pipefail; d=$(mktemp -d); trap '\''rm -rf "$d"'\'' EXIT; git -C /opt/ceo-orchestrator fetch origin master; git -C /opt/ceo-orchestrator show b2a1ec965f3213c26fa08d13b74b5a9cfec5dfc4:ops/isolation/install-isolated-runtime.py > "$d/install.py"; chmod 600 "$d/install.py"; echo "5fd8cb624f29bd37fd9e7f19b6485de89a8770ef6c28c3eeb9f5cc950cc1f034  $d/install.py" | sha256sum -c -; sudo python3 "$d/install.py"'
```

Никакой код не загружается и не исполняется от root через curl pipe. SHA фиксирует проверенную версию. Installer использует только стандартную библиотеку Python, не импортирует код проекта и не читает его секреты.

## Что делает

- Создаёт только новую системную identity ceo-w2p-agent с nologin, без дополнительных групп.
- Создаёт root-owned /var/lib/100print-isolation/rootfs и отдельную writable workspace этой identity.
- Устанавливает root-owned oneshot unit 100print-isolation-check.service; unit не включён в автозапуск и не запускает агента.
- Проверяет реальный запуск непривилегированного процесса в RootDirectory: недоступность проекта/host canary/секретных путей, запрет записи политики, запрет IPv4/IPv6 sockets, наследование запрета дочерним процессом, запрет symlink escape и NoNewPrivileges.
- Только после успешного выхода unit сохраняет root-owned /var/lib/100print-isolation/baseline-evidence.json со статусом HOST_BASELINE_READY_NOT_HERMES_READY.
- Повторный запуск сначала инвалидирует старый receipt; при ошибке статус FAILED_CLOSED_NOT_READY. Существующая чужая identity, небезопасные symlink/права или отличающийся unit вызывают отказ.

Для базовой проверки системные зависимости /usr (включая /usr/local) смонтированы read-only, а /bin,/lib,/lib64 следуют layout дистрибутива. Это **не** окончательная curated production rootfs. В рабочем runtime нужны только отдельно проверенные зависимости. /opt проекта, /home, host /etc, /run и Docker socket не смонтированы.

## Что не меняет

Не изменяет сайт, ботов, существующие systemd services, shared account/credentials, бизнес-БД, application guards или триггеры. Не создаёт issue23-host-review-approved и не считает его доказательством безопасности. Не устанавливает пакеты и не открывает сеть.

## Проверка результата

```bash
sudo cat /var/lib/100print-isolation/baseline-evidence.json
sudo journalctl -u 100print-isolation-check.service -n 10 --no-pager
```

При ошибке installer завершится ненулевым кодом и напечатает FAILED_CLOSED. Не отключать guards вручную.

## Что ещё обязательно для запуска Hermes

1. Доверенные брокеры доступа к LLM, публичным исследованиям и ресурсам только проекта; сырые GitHub/Telegram/DB/SSH credentials не передавать агентам.
2. Реальный isolated_executor и интеграция Hermes/Codex с этими брокерами вместо общего UID. Установка baseline не реализует этот отсутствующий компонент.
3. Реальный E2E Hermes + executor, проверка допустимых операций и отказов, независимая приёмка.
4. Только затем проверенное изменение dispatch/guards. Оно не выполняется этим installer автоматически.

## Локальная проверка без sudo

```bash
python3 ops/isolation/install-isolated-runtime.py --self-test
```

Перед публикацией прошли Python compile, три self-tests и systemd-analyze verify сгенерированного unit. Реальная установка на VPS ещё не выполнена из сессии разработки.
