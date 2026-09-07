from sqlalchemy import Column, Integer, String , Enum as SqlAlchemyEnum, ForeignKey
from app.db.database import Base
from enum import Enum
from sqlalchemy.orm import relationship

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(
        SqlAlchemyEnum(
            MessageRole,
            name="message_role",
            create_constraint=True,
            validate_strings=True
        ), 
        index=True,
        nullable=False
    )
    content = Column(String, nullable=False, index=True)
    created_at = Column(String, index=True)

    conversation = relationship("Conversation", back_populates="messages")