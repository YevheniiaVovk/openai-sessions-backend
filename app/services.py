from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from google import genai

from app.config import settings
from app.models import SessionModel, MessageModel

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:

    if model not in settings.MODEL_PRICING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model}' is not supported. Available models: {list(settings.MODEL_PRICING.keys())}"
        )
    
    pricing = settings.MODEL_PRICING[model]
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


class BaseLLMService(ABC):
    @abstractmethod
    async def generate_response(self, model_name: str, messages: list) -> Tuple[str, int, int]:
        pass


class GeminiLLMService(BaseLLMService):
    def __init__(self):
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

            in_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            out_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            text = response.text or ""

            return text, in_tokens, out_tokens
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM Provider Error: {str(e)}")


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
            text = response.choices[0].message.content or ""
            in_tokens = response.usage.prompt_tokens if response.usage else 0
            out_tokens = response.usage.completion_tokens if response.usage else 0
            return text, in_tokens, out_tokens
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {str(e)}")


def get_llm_service() -> BaseLLMService:
    if settings.USE_GEMINI_PROVIDER:
        return GeminiLLMService()
    return OpenAILLMService()



async def reset_session_generation(db: AsyncSession, session_obj: SessionModel, user_id: str) -> None:
    """Increments the generation, clears the context"""
    if session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    session_obj.generation += 1
    session_obj.total_tokens = 0
    session_obj.total_cost = 0.0
    await db.commit()


async def process_chat(
    db: AsyncSession, 
    session_obj: SessionModel, 
    user_id: str, 
    user_content: str,
    custom_model: Optional[str] = None  
):
    if session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session")

    
    model_to_use = custom_model or session_obj.model
    
    
    if model_to_use not in settings.MODEL_PRICING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_to_use}' is not supported. Available models: {list(settings.MODEL_PRICING.keys())}"
        )
    
    user_msg = MessageModel(
        session_id=session_obj.id,
        role="user",
        content=user_content,
        generation=session_obj.generation  
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    
    stmt = (
        select(MessageModel)
        .where(
            MessageModel.session_id == session_obj.id,
            MessageModel.generation == session_obj.generation  
        )
        .order_by(MessageModel.created_at.desc())
        .limit(15)
    )
    result = await db.execute(stmt)
    history = list(reversed(result.scalars().all()))

    openai_messages = [{"role": msg.role, "content": msg.content} for msg in history]

    
    llm = get_llm_service()
    assistant_content, in_tokens_raw, out_tokens_raw = await llm.generate_response(
        model_to_use, openai_messages  
    )

    in_tokens = int(in_tokens_raw or 0)
    out_tokens = int(out_tokens_raw or 0)

    
    cost = calculate_cost(model_to_use, in_tokens, out_tokens)

    
    assistant_msg = MessageModel(
        session_id=session_obj.id,
        role="assistant",
        content=assistant_content,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        message_cost=cost,
        generation=session_obj.generation 
    )
    
    
    current_tokens = int(session_obj.total_tokens or 0)
    current_cost = float(session_obj.total_cost or 0)

    session_obj.total_tokens = current_tokens + in_tokens + out_tokens
    session_obj.total_cost = current_cost + cost

    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return user_msg, assistant_msg