import jwt
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models import SessionModel
from app import schemas, services

router = APIRouter(prefix="/api/v1", tags=["Sessions"])

security = HTTPBearer()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("user_id") or payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing 'user_id' or 'sub'"
            )
        return str(user_id)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired JWT token"
        )


@router.post("/sessions", response_model=schemas.SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: schemas.SessionCreate, 
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    model = payload.model or settings.DEFAULT_MODEL
    
    if model not in settings.MODEL_PRICING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model}' is not supported. Available models: {list(settings.MODEL_PRICING.keys())}"
        )
    
    new_session = SessionModel(user_id=user_id, model=model)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session


@router.post("/sessions/{session_id}/messages", response_model=schemas.SendMessageResponse)
async def send_message(
    session_id: str, 
    payload: schemas.MessageCreate, 
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    
    user_msg, assistant_msg = await services.process_chat(
        db, session_obj, user_id, payload.content, payload.model
    )

    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "session_totals": {
            "total_tokens": session_obj.total_tokens,
            "total_cost": session_obj.total_cost
        }
    }



@router.post("/sessions/{session_id}/reset", response_model=schemas.ResetSessionResponse)
async def reset_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Reset session context—increments the generation and clears the context.
    The session ID remains the same, but the generation increases.
    """
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    
    
    await services.reset_session_generation(db, session_obj, user_id)
    
    return {
        "session_id": session_id,
        "message": f"Session reset. Generation incremented to {session_obj.generation}",
        "total_tokens": session_obj.total_tokens,
        "total_cost": session_obj.total_cost
    }


@router.get("/sessions/{session_id}", response_model=schemas.SessionDetailResponse)
async def get_session_history(
    session_id: str, 
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(SessionModel)
        .options(selectinload(SessionModel.messages))
        .where(SessionModel.id == session_id)
    )
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()

    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_obj.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this session")

    
    active_messages = [msg for msg in session_obj.messages if msg.generation == session_obj.generation]
    active_messages.sort(key=lambda m: m.created_at)
    session_obj.messages = active_messages
    
    return session_obj