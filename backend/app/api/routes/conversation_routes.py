import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents.support_graph import PENDING_APPROVAL_MESSAGE, stream_support_graph


def _chunk_token(chunk) -> str:
    """Normalize AIMessageChunk.content to a plain string.

    Groq/OpenAI return a str; Bedrock may return a list of content blocks
    like [{"type": "text", "text": "..."}]. Both cases are handled here.
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return content or ""
from app.api.dependencies import get_conversation_service, get_db
from app.models.conversations import Conversation
from app.models.messages import Message, MessageRole
from app.schemas.conversation_schema import ConversationCreateRequest, ConversationResponse
from app.schemas.message_schema import AssistantResponse, MessageCreateRequest
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
    return conversation


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    user_id: int,
    service: ConversationService = Depends(get_conversation_service),
):
    return service.list_conversations(user_id)


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
    response_model=AssistantResponse,
    status_code=201,
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


@router.post("/{conversation_id}/messages/stream")
def stream_message(
    conversation_id: int,
    message_data: MessageCreateRequest,
    db: Session = Depends(get_db),
):
    """
    SSE endpoint — streams agent lifecycle events as the graph executes.

    Event shape: data: {"event": "<name>", "data": {...}}

    Events emitted:
      agent_started        — graph execution begins
      thinking             — intent classification in progress
      retrieving_documents — RAG retrieval in progress
      tool_started         — a lookup/action tool is running
      tool_completed       — tool finished
      approval_required    — action needs human approval (graph paused)
      response_token       — one LLM output token (streamed)
      agent_completed      — final response ready; includes requires_approval flag
      error                — unhandled exception
    """
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Persist user message before streaming begins so it lands in DB immediately.
    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=message_data.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    db.commit()

    def generate():
        final_response = None
        requires_approval = False
        approval_status = None

        yield f"data: {json.dumps({'event': 'agent_started', 'data': {}})}\n\n"

        try:
            for mode, data in stream_support_graph(
                db,
                message_data.content,
                str(conversation.user_id),
                str(conversation_id),
            ):
                if mode == "custom":
                    # data is the dict passed to get_stream_writer() inside a node.
                    yield f"data: {json.dumps(data)}\n\n"

                elif mode == "messages":
                    # data is (AIMessageChunk, metadata).
                    chunk, meta = data
                    token = _chunk_token(chunk)
                    # Only surface tokens from response_node — not the JSON
                    # output from classify_node's structured-output LLM call.
                    if meta.get("langgraph_node") == "response" and token:
                        yield f"data: {json.dumps({'event': 'response_token', 'data': {'token': token}})}\n\n"

                elif mode == "updates":
                    # data is {node_name: state_delta}; capture final values.
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

        # Graph paused at interrupt() — approval pending.
        if final_response is None:
            final_response = PENDING_APPROVAL_MESSAGE
            requires_approval = True
            approval_status = "pending"

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