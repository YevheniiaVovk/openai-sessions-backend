import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple, Optional, AsyncGenerator
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

    @abstractmethod
    async def generate_stream(self, model_name: str, messages: list) -> AsyncGenerator[str, None]:
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
                model=model_name if model_name.startswith("gemini") else "gemini-2.5-flash",
                contents=formatted_contents,
                config={"system_instruction": system_instruction} if system_instruction else None
            )

            in_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            out_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            text = response.text or ""

            return text, in_tokens, out_tokens
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM Provider Error: {str(e)}")

    async def generate_stream(self, model_name: str, messages: list) -> AsyncGenerator[str, None]:
        
        try:
            formatted_contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            response = self.client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=formatted_contents
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"[Error: {str(e)}]"


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

    async def generate_stream(self, model_name: str, messages: list) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as e:
            yield f"[Error: {str(e)}]"


def get_llm_service() -> BaseLLMService:
    if getattr(settings, "USE_GEMINI_PROVIDER", False):
        return GeminiLLMService()
    return OpenAILLMService()


async def reset_session_generation(db: AsyncSession, session_obj: SessionModel, user_id: str) -> None:
    if session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    session_obj.generation += 1
    session_obj.total_tokens = 0
    session_obj.total_cost = 0.0
    await db.commit()


async def _get_context_history(db: AsyncSession, session_id: str, generation: int) -> list:
    """Витягує попередню історію до створення нового повідомлення"""
    stmt = (
        select(MessageModel)
        .where(
            MessageModel.session_id == session_id,
            MessageModel.generation == generation
        )
        .order_by(MessageModel.created_at.desc())
        .limit(14)  
    )
    result = await db.execute(stmt)
    history = list(reversed(result.scalars().all()))
    return [{"role": msg.role, "content": msg.content} for msg in history]


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

    
    openai_messages = await _get_context_history(db, session_obj.id, session_obj.generation)
    openai_messages.append({"role": "user", "content": user_content})

    
    user_msg = MessageModel(
        session_id=session_obj.id,
        role="user",
        content=user_content,
        generation=session_obj.generation  
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    
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
    
    session_obj.total_tokens = int(session_obj.total_tokens or 0) + in_tokens + out_tokens
    session_obj.total_cost = float(session_obj.total_cost or 0) + cost

    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return user_msg, assistant_msg


async def process_chat_stream(
    db: AsyncSession,
    session_obj: SessionModel,
    user_id: str,
    user_content: str,
    custom_model: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Стримінгова версія для Creative Challenge (Server-Sent Events)"""
    if session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    model_to_use = custom_model or session_obj.model
    if model_to_use not in settings.MODEL_PRICING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_to_use}' is not supported"
        )

    openai_messages = await _get_context_history(db, session_obj.id, session_obj.generation)
    openai_messages.append({"role": "user", "content": user_content})

    user_msg = MessageModel(
        session_id=session_obj.id,
        role="user",
        content=user_content,
        generation=session_obj.generation
    )
    db.add(user_msg)
    await db.commit()

    llm = get_llm_service()
    full_response = ""

    async for chunk in llm.generate_stream(model_to_use, openai_messages):
        full_response += chunk
        # SSE format
        yield f"data: {json.dumps({'content': chunk})}\n\n"

    
    in_tokens = len(user_content) // 4
    out_tokens = len(full_response) // 4
    cost = calculate_cost(model_to_use, in_tokens, out_tokens)

    assistant_msg = MessageModel(
        session_id=session_obj.id,
        role="assistant",
        content=full_response,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        message_cost=cost,
        generation=session_obj.generation
    )
    session_obj.total_tokens = int(session_obj.total_tokens or 0) + in_tokens + out_tokens
    session_obj.total_cost = float(session_obj.total_cost or 0) + cost

    db.add(assistant_msg)
    await db.commit()
    
    yield "data: [DONE]\n\n"