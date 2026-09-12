from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_conversation_service
from app.schemas.conversation_schema import ConversationCreateRequest, ConversationResponse
from app.schemas.message_schema import ChatResponse, MessageCreateRequest
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    service: ConversationService = Depends(get_conversation_service),
):
    conversation = service.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.post("", response_model=ConversationResponse, status_code=201)
def create_new_conversation(
    conversation_data: ConversationCreateRequest,
    service: ConversationService = Depends(get_conversation_service),
):
    try:
        return service.create_conversation(conversation_data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/{conversation_id}/messages",
    response_model=ChatResponse,
)
def create_message(
    conversation_id: int,
    message_data: MessageCreateRequest,
    service: ConversationService = Depends(get_conversation_service),
):
    try:
        response = service.add_message(conversation_id, message_data)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if response is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return response