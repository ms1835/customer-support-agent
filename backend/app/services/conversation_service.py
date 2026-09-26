from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message, MessageRole
from app.models.users import User
from app.schemas.conversation_schema import ConversationCreateRequest
from app.schemas.message_schema import AssistantResponse, MessageCreateRequest
from app.agents.support_graph import resume_support_graph, run_support_graph
from langgraph.errors import GraphInterrupt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone


_PENDING_APPROVAL_MESSAGE = (
    "Your request has been received and is pending approval. "
    "Please review the details and approve or reject below."
)


class ConversationService:

    def __init__(self, db: Session):
        self.db = db

    def get_conversation_by_id(self, conversation_id: int) -> Conversation | None:
        query = select(Conversation).where(Conversation.id == conversation_id)
        return self.db.scalar(query)

    def list_conversations(self, user_id: int) -> list[Conversation]:
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
        return list(self.db.scalars(query).all())

    def create_conversation(self, conversation_data: ConversationCreateRequest) -> Conversation:
        if self.db.get(User, conversation_data.user_id) is None:
            raise ValueError("User does not exist")

        conversation = Conversation(
            user_id=conversation_data.user_id,
            status=ConversationStatus.OPEN,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        try:
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception:
            self.db.rollback()
            raise

    def add_message(
        self,
        conversation_id: int,
        message_data: MessageCreateRequest,
    ) -> AssistantResponse | None:
        conversation = self.db.get(Conversation, conversation_id)
        if conversation is None:
            return None

        user_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=message_data.content,
            created_at=datetime.now(timezone.utc),
        )

        try:
            self.db.add(user_message)
            self.db.flush()

            try:
                # History is restored from the PostgreSQL checkpoint by LangGraph.
                # conversation_id maps 1-to-1 with thread_id in the checkpoint store.
                graph_state = run_support_graph(
                    self.db,
                    message_data.content,
                    str(conversation.user_id),
                    str(conversation_id),
                )
            except GraphInterrupt:
                graph_state = {}

            response_text = graph_state.get("final_response")
            if response_text is None:
                # Graph paused at interrupt() in approval_node — waiting for
                # human decision via POST /api/agent/{thread_id}/resume
                response_text = _PENDING_APPROVAL_MESSAGE
                requires_approval = True
                approval_status = "pending"
            else:
                requires_approval = graph_state.get("requires_approval", False)
                approval_status = graph_state.get("approval_status")

            assistant_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(assistant_message)
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return AssistantResponse(
                response=response_text,
                requires_approval=requires_approval,
                approval_status=approval_status,
            )
        except Exception:
            self.db.rollback()
            raise

    def resume_conversation(
        self,
        thread_id: str,
        decision: str,
    ) -> AssistantResponse | None:
        """
        Resume a graph paused by interrupt() in approval_node.
        thread_id == str(conversation_id).
        decision: "approve" | "reject"
        """
        conversation_id = int(thread_id)
        conversation = self.db.get(Conversation, conversation_id)
        if conversation is None:
            return None

        graph_state = resume_support_graph(self.db, thread_id, decision)
        response_text = graph_state["final_response"]

        assistant_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(assistant_message)
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return AssistantResponse(
            response=response_text,
            requires_approval=graph_state.get("requires_approval", False),
            approval_status=graph_state.get("approval_status"),
        )
