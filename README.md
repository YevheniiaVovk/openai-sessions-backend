# OpenAI Chat Sessions Backend

Асинхронний backend-сервіс на FastAPI для управління сесіями чату з LLM, підтримкою підрахунку токенів та кастомною політикою ціноутворення.

---

## 🚀 Основні можливості

- **Управління сесіями:** створення нових сесій та збереження всієї історії діалогу у БД MySQL.
- **Асинхронна робота:** використання FastAPI, AsyncSQLAlchemy та `aiomysql`.
- **Автоматичний підрахунок токенів та вартості:** підрахунок `input` і `output` токенів для кожного повідомлення та накопичувальний підрахунок для сесії.
- **Підтримка LLM-провайдерів:** підключення OpenAI API та адаптера Google Gemini.

---

## 💰 Pricing Policy

- **Model:** `gpt-5.6-terra`
- **Input tokens:** $0.002 / 1k tokens
- **Output tokens:** $0.012 / 1k tokens

---

## 🛠️ Встановлення та запуск

### 1. Налаштування змінних оточення

Створіть файл `.env` на основі прикладу:

```bash
cp .env.example .env
```

Заповніть потрібні ключі доступу (`OPENAI_API_KEY` або `GEMINI_API_KEY`) у файлі `.env`.

### 2. Запуск через Docker Compose (рекомендовано)

Запустіть додаток разом із базою даних MySQL у контейнерах:

```bash
docker compose up --build
```

Сервер буде доступний за адресою: <http://localhost:8000>.

### 3. Локальний запуск із менеджером пакетів `uv`

Встановіть залежності:

```bash
uv sync
```

Запустіть міграції бази даних:

```bash
uv run alembic upgrade head
```

Запустіть сервер розробки:

```bash
uv run uvicorn app.main:app --reload
```

---

## 📖 Інтерактивна документація API

Після запуску сервера документація Swagger UI та ReDoc доступні за посиланнями:

- **Swagger UI:** <http://localhost:8000/docs>
- **ReDoc:** <http://localhost:8000/redoc>

---

## 🔐 Аутентифікація

Усі endpoints вимагають JWT-токен у заголовку:

```http
Authorization: Bearer <JWT_TOKEN>
```

Токен повинен містити claim `user_id` або `sub`.

---

## 📁 Структура проєкту

```text
openai-sessions-backend/
├── alembic/                    # Міграції бази даних Alembic
├── app/
│   ├── __init__.py             # Package init
│   ├── config.py               # Конфіги та pricing-конфігурація
│   ├── database.py             # SQLAlchemy async setup
│   ├── models.py               # ORM-моделі (Session, Message)
│   ├── schemas.py              # Pydantic DTOs для валідації
│   ├── services.py              # Бізнес-логіка (контекст, OpenAI, БД)
│   ├── routes.py                # REST API endpoints
│   └── main.py                  # FastAPI app init
├── tests/                      # Тестовий модуль
├── .env.example                # Приклад env-файлу
├── .gitignore
├── alembic.ini                 # Конфіг Alembic
├── docker-compose.yml           # Docker Compose конфіг
├── pyproject.toml               # Залежності проєкту (uv)
├── uv.lock                      # Lock-файл залежностей
└── README.md                    # Документація проєкту
```
