from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SqlAlchemyEnum,
    Integer,
    String,
    func,  # used for updated_at onupdate
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class UserRole(str, Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"


class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    role = Column(
        SqlAlchemyEnum(
            UserRole, name="user_role", create_constraint=False,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=UserRole.CUSTOMER,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    invite_token = Column(String, nullable=True, index=True)
    invite_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Agent-only fields (null for customers/admins)
    agent_status = Column(
        SqlAlchemyEnum(
            AgentStatus, name="agent_status", create_constraint=False,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=True,
        index=True,
    )
    current_ticket_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    orders = relationship("Order", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
    assigned_tickets = relationship(
        "SupportTicket",
        foreign_keys="SupportTicket.assigned_agent_id",
        back_populates="assigned_agent",
    )
