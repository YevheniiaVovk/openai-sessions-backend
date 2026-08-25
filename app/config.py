import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    USE_GEMINI_PROVIDER: bool = os.getenv("USE_GEMINI_PROVIDER", "true").lower() == "true"
    
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "mysql+aiomysql://root:password@localhost:3306/chat_db"
    )
    
    DEFAULT_MODEL: str = "gpt-5.6-terra"
    
    
    MODEL_PRICING: dict = {
        # ===== OPENAI =====
        "gpt-5.6-terra": {
            "input": 0.002,
            "output": 0.012,
        },
        "gpt-4o": {
            "input": 0.005,
            "output": 0.015,
        },
        "gpt-4o-mini": {
            "input": 0.00015,
            "output": 0.0006,
        },
        
        # ===== GEMINI =====
        "gemini-3.6-flash": {
            "input": 0.00075,
            "output": 0.003,
        },
        "gemini-3.6-flash-lite": {
            "input": 0.0001,
            "output": 0.0004,
        },
        "gemini-3.1-pro": {
            "input": 0.0015,
            "output": 0.006,
        }
    }

    class Config:
        env_file = ".env"

settings = Settings()