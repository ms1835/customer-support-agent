from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)

    orders = relationship("Order", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")