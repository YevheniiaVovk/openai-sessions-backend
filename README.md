# OpenAI Chat Backend Service

## Pricing Policy
- **Model**: `gpt-5.6-terra`
- **Input**: $0.002 / 1k tokens
- **Output**: $0.012 / 1k tokens

## Setup & Run
```bash
pip install fastapi uvicorn sqlalchemy aiosqlite openai pydantic-settings
uvicorn main:app --reload