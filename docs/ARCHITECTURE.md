# ARCHITECTURE

## Верхний уровень

```text
Telegram
   |
Input Gateway
   |
Intent + Department Router
   |
Context Builder <----> Long-term Memory
   |                    PostgreSQL + pgvector
   |
Organization Orchestrator
   |
   +--> Department Head
   |       +--> Specialist Agent
   |       +--> Specialist Agent
   |       +--> Skills
   |
   +--> Cross-Department Council
           +--> Strategy
           +--> Marketing
           +--> SEO
           +--> Sales
           +--> Finance
           +--> Operations
           +--> Critic
   |
Chief of Staff / Synthesis
   |
Decision + Action Plan
   |
Memory + Telegram response
```

## Роли

### CEO / Chief of Staff Orchestrator
Определяет уровень задачи, собирает контекст, выбирает подразделения, запускает дискуссию и принимает структурированный результат от руководителей.

### Department Head
Получает бизнес-задачу, декомпозирует её, назначает специалистов, запрашивает данные у других подразделений и формирует позицию своего подразделения.

### Specialist Agent
Работает в узкой профессиональной области и использует skills/tools.

### Critic
Ищет ошибки, слабые допущения, риски и альтернативы.

## Маршрутизация

Запрос проходит четыре уровня:

1. Intent: мысль / вопрос / задача / анализ / решение.
2. Project: к какому проекту относится.
3. Department: кто владелец задачи.
4. Complexity:
   - L1: ответ одного агента;
   - L2: руководитель + специалисты;
   - L3: несколько подразделений;
   - L4: полный AI Council.

## Память

Храним не только сообщения, а сущности:
- thought
- idea
- question
- task
- decision
- hypothesis
- problem
- insight
- fact
- goal
- risk
- plan
- result

Связи:
- supports
- continues
- expands
- contradicts
- duplicates
- replaces
- depends_on
- implements
- related_to

Поиск гибридный:
semantic + full text + metadata + recency + importance.

## Provider abstraction

Все обращения к LLM идут через `BrainProvider`.

Никакой агент не должен напрямую зависеть от конкретного поставщика модели.
