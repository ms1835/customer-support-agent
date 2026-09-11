from app.models.conversations import Conversation, ConversationStatus
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
            status=ConversationStatus.OPEN,
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

    def chat(self, conversation_id: int, content: str) -> Message | None:
        if self.db.get(Conversation, conversation_id) is None:
            return None

        user_message = Message(
            conversation_id=conversation_id,
            role=MESSAGE_ROLE_USER,
            content=content,
        )
        try:
            self.db.add(user_message)
            self.db.commit()
            self.db.refresh(user_message)

            assistant_text = LLM.invoke({
                "conversation_id": conversation_id,
                "message": content,
            })

            assistant_message = Message(
                conversation_id=conversation_id,
                role=MESSAGE_ROLE_ASSISTANT,
                content=assistant_text,
            )

            self.db.add(assistant_message)
            self.db.commit()
            self.db.refresh(assistant_message)
            
            return user_message
        except Exception:
            self.db.rollback()
            raise