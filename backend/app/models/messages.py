from sqlalchemy import Column, Integer, String , Enum as SqlAlchemyEnum
from databse import Base
from enum import Enum

def MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

def Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, foreign_key="conversations.id", index=True)
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
    content = Column(String, index=True)
    created_at = Column(String, index=True)