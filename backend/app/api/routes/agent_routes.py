import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.support_graph import stream_resume_graph


def _chunk_token(chunk) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return content or ""
from app.api.dependencies import get_current_user, get_db
from app.models.conversations import Conversation
from app.models.messages import Message, MessageRole
from app.models.users import User
from app.schemas.agent_schema import ResumeRequest
from app.schemas.message_schema import AssistantResponse
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/{thread_id}/resume", response_model=AssistantResponse)
def resume_agent(
    thread_id: str,
    body: ResumeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Resume a paused graph (non-streaming)."""
    service = ConversationService(db)
    response = service.resume_conversation(thread_id, body.decision)
    if response is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return response


@router.post("/{thread_id}/resume/stream")
def stream_resume_agent(
    thread_id: str,
    body: ResumeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Resume a paused LangGraph thread with SSE streaming.
    Called by the frontend after the user approves or rejects.

    Streams: tool_started / tool_completed (execute_action), response_token,
             agent_completed with final response and approval_status.
    """
    conversation_id = int(thread_id)
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    decision = body.decision

    def generate():
        final_response = None
        requires_approval = False
        approval_status = None

        yield f"data: {json.dumps({'event': 'agent_started', 'data': {}})}\n\n"

        try:
            for mode, data in stream_resume_graph(db, thread_id, decision):
                if mode == "custom":
                    yield f"data: {json.dumps(data)}\n\n"

                elif mode == "messages":
                    chunk, meta = data
                    token = _chunk_token(chunk)
                    if meta.get("langgraph_node") == "response" and token:
                        yield f"data: {json.dumps({'event': 'response_token', 'data': {'token': token}})}\n\n"

                elif mode == "updates":
                    for delta in data.values():
                        if not isinstance(delta, dict):
                            continue
                        if delta.get("final_response") is not None:
                            final_response = delta["final_response"]
                        if delta.get("requires_approval") is not None:
                            requires_approval = delta["requires_approval"]
                        if delta.get("approval_status") is not None:
                            approval_status = delta["approval_status"]

        except Exception as exc:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(exc)}})}\n\n"
            return

        if final_response is None:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'No response generated after resume.'}})}\n\n"
            return

        # Persist assistant message.
        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=final_response,
            created_at=datetime.now(timezone.utc),
        ))
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()

        yield f"data: {json.dumps({'event': 'agent_completed', 'data': {'response': final_response, 'requires_approval': requires_approval, 'approval_status': approval_status}})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
