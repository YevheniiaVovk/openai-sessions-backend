from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

class SessionCreate(BaseModel):
    model: Optional[str] = None

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    input_tokens: int
    output_tokens: int
    message_cost: float
    created_at: datetime

    class Config:
        from_attributes = True

class SessionResponse(BaseModel):
    id: str
    model: str
    total_tokens: int
    total_cost: float
    created_at: datetime

    class Config:
        from_attributes = True

class SessionDetailResponse(SessionResponse):
    messages: List[MessageResponse]

class SendMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    session_totals: dict