from abc import ABC, abstractmethod
from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from google import genai

from app.config import settings
from app.models import SessionModel, MessageModel

# Cost Estimate (General)
def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = settings.MODEL_PRICING.get(model, settings.MODEL_PRICING["gpt-5.6-terra"])
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


class BaseLLMService(ABC):
    @abstractmethod
    async def generate_response(self, model_name: str, messages: list) -> Tuple[str, int, int]:
        """Return (text_response, input_tokens, output_tokens)"""
        pass


class GeminiLLMService(BaseLLMService):
    def __init__(self):
        # google-genai
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_response(self, model_name: str, messages: list) -> Tuple[str, int, int]:
        try:
            system_instruction = None
            formatted_contents = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                else:
                    role = "user" if msg["role"] == "user" else "model"
                    formatted_contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=formatted_contents,
                config={"system_instruction": system_instruction} if system_instruction else None
            )

            in_tokens = response.usage_metadata.prompt_token_count or 0
            out_tokens = response.usage_metadata.candidates_token_count or 0
            text = response.text or ""

            return text, in_tokens, out_tokens
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM Provider Error: {str(e)}")


# A ready-to-use class for OpenAI (in case the testers want to substitute their own OPENAI_API_KEY)
class OpenAILLMService(BaseLLMService):
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_response(self, model_name: str, messages: list) -> Tuple[str, int, int]:
        try:
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            text = response.choices[0].message.content
            in_tokens = response.usage.prompt_tokens
            out_tokens = response.usage.completion_tokens
            return text, in_tokens, out_tokens
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")


# Choosing a Provider
def get_llm_service() -> BaseLLMService:
    if settings.USE_GEMINI_PROVIDER:
        return GeminiLLMService()
    return OpenAILLMService()


async def process_chat(db: AsyncSession, session_obj: SessionModel, user_content: str):
    stmt = (
        select(MessageModel)
        .where(MessageModel.session_id == session_obj.id)
        .order_by(MessageModel.created_at.desc())
        .limit(15)
    )
    result = await db.execute(stmt)
    history = list(reversed(result.scalars().all()))

    openai_messages = [{"role": msg.role, "content": msg.content} for msg in history]
    openai_messages.append({"role": "user", "content": user_content})

    llm = get_llm_service()
    assistant_content, in_tokens, out_tokens = await llm.generate_response(
        session_obj.model, openai_messages
    )

    cost = calculate_cost(session_obj.model, in_tokens, out_tokens)

    user_msg = MessageModel(
        session_id=session_obj.id,
        role="user",
        content=user_content
    )
    assistant_msg = MessageModel(
        session_id=session_obj.id,
        role="assistant",
        content=assistant_content,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        message_cost=cost
    )
    
    session_obj.total_tokens += (in_tokens + out_tokens)
    session_obj.total_cost += cost

    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return user_msg, assistant_msg