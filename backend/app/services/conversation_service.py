from app.models.conversations import Conversation, ConversationStatus
from app.models.messages import Message, MessageRole
from app.models.users import User
from app.schemas.conversation_schema import ConversationCreateRequest
from app.schemas.message_schema import AssistantResponse, MessageCreateRequest
from app.services.llm_service import generate_intent, generate_response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone

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

            intent = generate_intent(message_data.content)
            if intent.category == "unknown":
                response_text = (
                    "That question is outside my support scope. "
                    "I can help with products, orders, shipments, refunds, "
                    "and cancellations."
                )
            else:
                response_text = generate_response(message_data.content, intent)
            assistant_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(assistant_message)
            conversation.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return AssistantResponse(response=response_text)
        except Exception:
            self.db.rollback()
            raise
