from app.models.conversations import Conversation
from sqlalchemy.orm import Session
from app.schemas.conversation_schema import ConversationCreateRequest

def get_conversation_by_id(db: Session, conversation_id: int) -> Conversation | None:
    query = select(Conversation).where(Conversation.id == conversation_id)
    return db.scalar(query)