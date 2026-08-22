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
        "gpt-5.6-terra": {
            "input": 0.002,
            "output": 0.012,
        }
    }

    class Config:
        env_file = ".env"

settings = Settings()