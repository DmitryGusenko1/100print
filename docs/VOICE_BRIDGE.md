# Voice bridge #8

Постоянный транспорт: https://github.com/DmitryGusenko1/100print/issues/8.
Входные комментарии принимаются только от владельца DmitryGusenko1:

```text
CHATGPT_IN
session=<unique chat session>
message=<user question, multiline allowed>
```

```text
CHATGPT_OUT
session=<same session>
task_id=<durable UUID>
result=<JSON>
```

В конце OUT есть HTML marker с task_id для восстановления доставки после сбоя.
Для CONTEXT и DECISION поле message начинается с отдельной строки `CONTEXT`
или `DECISION`; последующие строки содержат запрос контекста или явно принятое
решение. Ответ CONTEXT содержит context; DECISION — saved и memory_id.
Обычный текст создаёт analysis task с серверным контекстом и Critic.
Не повторять POST при ожидании; перечитывать комментарии, связывать OUT с session,
операцией, result.request_comment_id (ID входного комментария) и task_id. Для нескольких одновременных вопросов используйте разные session.
Аналитика занимает несколько минут; завершение Voice-реплики не отменяет серверную задачу.

Для нового Voice-чата (одно действие, GitHub plugin должен быть подключён):

> Используй GitHub plugin: прочитай docs/CHATGPT_PROJECT_INSTRUCTIONS.md в DmitryGusenko1/100print, следуй этим инструкциям и через bridge issue #8 проведи с Finance, Marketing, Sales и Critic анализ, стоит ли нам снизить цены на 15% ради быстрого роста, не соглашаясь автоматически.

Инструкции также можно заранее вставить в Project Instructions. Реальное выполнение
GitHub tools зависит от их доступности в выбранном ChatGPT Voice режиме и разрешений
аккаунта; VPS не может включить plugin или изменить настройки ChatGPT за пользователя.
Нет гарантии exactly-once POST при неопределённом результате GitHub HTTP запроса:
marker и перечитывание восстанавливают подтверждённую публикацию. Intake, cursor и
артефакты идемпотентны и транзакционны в ceo_orchestrator PostgreSQL.
