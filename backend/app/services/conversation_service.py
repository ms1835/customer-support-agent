from app.models.conversations import Conversation
from app.models.messages import Message
from app.models.users import User
from app.schemas.conversation_schema import ConversationCreateRequest
from app.schemas.message_schema import MessageCreateRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

class ConversationService:

    def __init__(self):
        pass

    def get_conversation_by_id(self, db: Session, conversation_id: int) -> Conversation | None:
        query = select(Conversation).where(Conversation.id == conversation_id)
        return db.scalar(query)


    def create_conversation(self, db: Session, conversation_data: ConversationCreateRequest) -> Conversation:
        if db.get(User, conversation_data.user_id) is None:
            raise ValueError("User does not exist")

        conversation = Conversation(
            user_id=conversation_data.user_id,
            status=conversation_data.status,
        )
        try:
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            return conversation
        except Exception:
            db.rollback()
            raise


    def add_message(self, db: Session, conversation_id: int, message_data: MessageCreateRequest) -> Message | None:
        if db.get(Conversation, conversation_id) is None:
            return None

        message = Message(
            conversation_id=conversation_id,
            role=message_data.role,
            content=message_data.content,
        )
        try:
            db.add(message)
            db.commit()
            db.refresh(message)
            return message
        except Exception:
            db.rollback()
            raise