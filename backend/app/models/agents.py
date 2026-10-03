from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlAlchemyEnum, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.database import Base


class AgentStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    status = Column(
        SqlAlchemyEnum(
            AgentStatus,
            name="agent_status",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=AgentStatus.AVAILABLE,
        index=True,
    )
    # Tracks how many open tickets are currently assigned to this agent.
    current_ticket_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    tickets = relationship("SupportTicket", back_populates="assigned_agent")
