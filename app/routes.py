from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models import SessionModel
from app import schemas, services

router = APIRouter(prefix="", tags=["Sessions"])

@router.post("/sessions", response_model=schemas.SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: schemas.SessionCreate, 
    db: AsyncSession = Depends(get_db)
):
    model = payload.model or settings.DEFAULT_MODEL
    new_session = SessionModel(model=model)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.post("/sessions/{session_id}/messages", response_model=schemas.SendMessageResponse)
async def send_message(
    session_id: str, 
    payload: schemas.MessageCreate, 
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SessionModel).where(SessionModel.id == session_id)
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg, assistant_msg = await services.process_chat(db, session_obj, payload.content)

    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "session_totals": {
            "total_tokens": session_obj.total_tokens,
            "total_cost": session_obj.total_cost
        }
    }

@router.get("/sessions/{session_id}", response_model=schemas.SessionDetailResponse)
async def get_session(
    session_id: str, 
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

    return session_obj