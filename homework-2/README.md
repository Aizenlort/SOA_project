# Marketplace API (SOA Homework 2)

RESTful API для управления маркетплейсом, реализующий принципы микросервисной архитектуры, подход Contract-First и сложную бизнес-логику с транзакционной целостностью.

## Стек технологий

- **Язык:** Python 3.11
- **Фреймворк:** FastAPI (Async)
- **База данных:** PostgreSQL 15
- **Миграции:** Flyway
- **Контейнеризация:** Docker & Docker Compose
- **ORM:** SQLAlchemy 2.0 (Async)
- **Валидация и DTO:** Pydantic V2 (Code Generation)
- **Безопасность:** JWT (Access + Refresh tokens), Passlib (Bcrypt)

## Быстрый запуск

Для запуска проекта требуется установленный Docker и Docker Compose.

1. Клонировать репозиторий и перейти в папку `homework-2`.
2. Запустить сборку и старт контейнеров:
   ```bash
   docker-compose up --build
   ```
3. Приложение будет доступно по адресу: `http://localhost:8000`
4. Интерактивная документация (Swagger UI): `http://localhost:8000/docs`
5. Альтернативная документация (ReDoc): `http://localhost:8000/redoc`

*Сгенерированный код (`src/api/models.py`) исключен из Git и автоматически генерируется на этапе сборки Docker-образа.*

##  Архитектура и принципы

Проект построен в соответствии с принципами REST и микросервисной архитектуры:

1. **Contract-First (Сначала контракт):** 
   Вся работа начинается с описания API в `openapi.yaml`. Pydantic-модели (DTO) генерируются автоматически с помощью `datamodel-code-generator`. Ручное создание DTO запрещено, что гарантирует 100% соответствие кода спецификации.
2. **Разделение ответственности (Clean Architecture):**
   - **Routers:** Прием HTTP-запросов, валидация зависимостей.
   - **Services:** Чистая бизнес-логика, работа с транзакциями.
   - **Models (ORM):** Маппинг на реляционную схему БД.
3. **Stateless:** Сервер не хранит состояние клиента между запросами. Аутентификация реализована через JWT-токены.

## Соответствие требованиям задания

| № | Требование | Реализация |
|---|------------|------------|
| **1** | OpenAPI спецификация | Файл `openapi.yaml` (версия 3.0.3), описывающий все эндпоинты, схемы и коды ошибок. |
| **2** | REST API и CRUD | Реализованы полные CRUD для Products, Orders, Promo Codes. Поддерживаются пагинация (`page`, `size`) и фильтрация (по статусу, категории, цене). |
| **3** | Code Generation | Скрипт `generate.py` и этап `RUN python generate.py` в `Dockerfile`. Сгенерированные файлы добавлены в `.gitignore`. |
| **4** | PostgreSQL + Миграции | Схема БД описана в SQL и применяется через **Flyway** при старте контейнера. Добавлены индексы (например, `idx_products_status`). |
| **5** | Единый формат ошибок | Все ошибки возвращают JSON: `{"error_code": "...", "message": "...", "details": {...}}`. |
| **6** | Валидация данных | Ограничения описаны в OpenAPI. Ошибки Pydantic перехвачены кастомным обработчиком и возвращают **HTTP 400** (`VALIDATION_ERROR`) вместо стандартного 422. |
| **7** | Бизнес-логика | Реализованы транзакции, резервирование остатков, проверка лимитов частоты (Rate Limiting), применение промокодов со скидками. |
| **8** | Логирование | Кастомный Middleware пишет JSON-логи в stdout. Включает `request_id`, `duration_ms`, `user_id`. Тело мутационных запросов логируется с маскировкой паролей. `request_id` пробрасывается в заголовок ответа `X-Request-Id`. |
| **9** | JWT Аутентификация | Выдача пары Access/Refresh токенов. Токены содержат claim `role`. |
| **10** | Ролевая модель | Разделение ролей (USER, SELLER, ADMIN). Ограничения описаны в OpenAPI (`securitySchemes`) и проверяются в зависимостях FastAPI. |

## Каталог кодов ошибок

API использует строгий набор кодов ошибок, описанных в спецификации:

- **400:** `VALIDATION_ERROR`
- **401:** `TOKEN_INVALID`, `TOKEN_EXPIRED`, `REFRESH_TOKEN_INVALID`, `INVALID_CREDENTIALS`
- **403:** `ACCESS_DENIED`, `ORDER_OWNERSHIP_VIOLATION`
- **404:** `PRODUCT_NOT_FOUND`, `ORDER_NOT_FOUND`
- **409:** `PRODUCT_INACTIVE`, `ORDER_HAS_ACTIVE`, `INVALID_STATE_TRANSITION`, `INSUFFICIENT_STOCK`, `EMAIL_ALREADY_EXISTS`
- **422:** `PROMO_CODE_INVALID`, `PROMO_CODE_MIN_AMOUNT`
- **429:** `ORDER_LIMIT_EXCEEDED`

## Структура проекта

```text
homework-2/
|--- db/migrations/      # SQL скрипты для Flyway
|--- src/
│   |--- api/            # Роутеры и сгенерированные DTO (models.py)
│   |--- core/           # Конфигурация, JWT утилиты, Logging Middleware
│   |--- db/             # Настройка Async SQLAlchemy
│   |--- models/         # ORM модели (SQLAlchemy)
│   |--- services/       # Бизнес-логика (Auth, Products, Orders, Promo)
│   |--- main.py         # Точка входа FastAPI
|--- docker-compose.yml  # Оркестрация сервисов (App, DB, Flyway)
|-- Dockerfile          # Сборка Python-образа
|-- generate.py         # Скрипт генерации кода из OpenAPI
|-- openapi.yaml        # Контракт API
```