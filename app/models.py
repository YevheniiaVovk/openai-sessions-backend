import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model = Column(String(50), nullable=False, default="gpt-5.6-terra")
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")

class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    message_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    session = relationship("SessionModel", back_populates="messages")