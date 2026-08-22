from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model: Optional[str] = "gpt-5.6-terra"


class SessionResponse(BaseModel):
    id: str
    user_id: str
    model: str
    total_tokens: int
    total_cost: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Content cannot be empty")


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    input_tokens: Optional[int] = 0
    output_tokens: Optional[int] = 0
    message_cost: Optional[float] = 0.0

    model_config = ConfigDict(from_attributes=True)


class SessionTotals(BaseModel):
    total_tokens: int
    total_cost: float


class SendMessageResponse(BaseModel):
    user_message: MessageItem
    assistant_message: MessageItem
    session_totals: SessionTotals


class SessionDetailResponse(BaseModel):
    id: str
    user_id: str
    model: str
    total_tokens: int
    total_cost: float
    created_at: datetime
    messages: List[MessageItem]

    model_config = ConfigDict(from_attributes=True)