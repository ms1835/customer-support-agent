from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import MessageRole
from app.models.users import User
from app.schemas.conversation_schema import ConversationCreateRequest
from app.schemas.message_schema import ChatResponse, MessageCreateRequest
from app.services.llm_service import generate_reply
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

class ConversationService:

    def __init__(self, db: Session):
        self.db = db

    def get_conversation_by_id(self, conversation_id: int) -> Conversation | None:
        query = select(Conversation).where(Conversation.id == conversation_id)
        return self.db.scalar(query)


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
    ) -> ChatResponse | None:
        if message_data.role != MessageRole.USER:
            raise ValueError("Only user messages can be sent to the assistant")

        return ChatResponse(message=generate_reply(message_data.content))
