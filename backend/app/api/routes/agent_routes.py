from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db
from app.schemas.agent_schema import ResumeRequest
from app.schemas.message_schema import AssistantResponse
from app.services.conversation_service import ConversationService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post(
    "/{thread_id}/resume",
    response_model=AssistantResponse,
)
def resume_agent(
    thread_id: str,
    body: ResumeRequest,
    db: Session = Depends(get_db),
):
    """
    Resume a LangGraph thread that was paused by an interrupt() in approval_node.
    Called by the frontend after the user approves or rejects the proposed action.
    """
    service = ConversationService(db)
    response = service.resume_conversation(thread_id, body.decision)
    if response is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return response
