from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.conversation_schema import ConversationCreateRequest, ConversationResponse
from app.schemas.message_schema import MessageCreateRequest, MessageResponse
from app.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    conversation = conversation_service.get_conversation_by_id(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationResponse, status_code=201)
def create_new_conversation(
    conversation_data: ConversationCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return conversation_service.create_conversation(db, conversation_data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
def create_message(
    conversation_id: int,
    message_data: MessageCreateRequest,
    db: Session = Depends(get_db),
):
    message = conversation_service.add_message(
        db,
        conversation_id,
        message_data,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return message

