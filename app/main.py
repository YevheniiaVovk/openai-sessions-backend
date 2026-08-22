from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import init_db
from app.routes import router as sessions_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="OpenAI Chat Sessions Backend",
    description="REST API for managing OpenAI chat sessions with usage tracking and cost calculation",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(sessions_router)