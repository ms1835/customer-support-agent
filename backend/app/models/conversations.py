from sqlalchemy import Column, Integer, String
from databse import Base

def Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, foreign_key="users.id", index=True)
    status = Column(String, index=True)
    created_at = Column(String, index=True)
    updated_at = Column(String, index=True)