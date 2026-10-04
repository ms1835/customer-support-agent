from enum import Enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SqlAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class TicketStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class EscalationType(str, Enum):
    USER_REQUESTED = "user_requested"
    AUTO_UNRESOLVED = "auto_unresolved"
    AUTO_FAILED_ACTION = "auto_failed_action"
    AUTO_SENTIMENT = "auto_sentiment"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)

    # One conversation → one ticket (unique ensures no duplicate tickets).
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_agent_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        SqlAlchemyEnum(
            TicketStatus,
            name="ticket_status",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=TicketStatus.OPEN,
        index=True,
    )
    priority = Column(
        SqlAlchemyEnum(
            TicketPriority,
            name="ticket_priority",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=TicketPriority.MEDIUM,
        index=True,
    )
    escalation_type = Column(
        SqlAlchemyEnum(
            EscalationType,
            name="escalation_type",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
        default=EscalationType.USER_REQUESTED,
    )

    # Human-readable reason logged at escalation time.
    escalation_reason = Column(String, nullable=False)
    # Internal notes added by the assigned agent.
    notes = Column(Text, nullable=True)

    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    conversation = relationship("Conversation", back_populates="ticket")
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id], back_populates="assigned_tickets")
    user = relationship("User", foreign_keys=[user_id])
