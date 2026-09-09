from app.models.conversations import Conversation
from app.models.messages import Message
from app.models.users import User
from app.schemas.conversation_schema import ConversationCreateRequest
from app.schemas.message_schema import MessageCreateRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

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
            status=conversation_data.status,
        )
        try:
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
            return conversation
        except Exception:
            self.db.rollback()
            raise

    def add_message(self, conversation_id: int, message_data: MessageCreateRequest) -> Message | None:
        if self.db.get(Conversation, conversation_id) is None:
            return None

        message = Message(
            conversation_id=conversation_id,
            role=message_data.role,
            content=message_data.content,
        )
        try:
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except Exception:
            self.db.rollback()
            raise