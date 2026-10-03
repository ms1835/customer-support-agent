from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.support_tickets import EscalationType, TicketPriority, TicketStatus


class EscalationRequest(BaseModel):
    """Posted to /api/conversations/{id}/escalate to trigger manual escalation."""
    reason: str | None = Field(
        default=None,
        description="Human-readable reason; auto-generated from intent if omitted.",
    )
    priority: TicketPriority = TicketPriority.MEDIUM


class AgentSummary(BaseModel):
    """Lightweight agent embed inside ticket responses — avoids circular imports."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    user_id: int
    assigned_agent_id: int | None
    assigned_agent: AgentSummary | None = None
    status: TicketStatus
    priority: TicketPriority
    escalation_type: EscalationType
    escalation_reason: str
    notes: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TicketAssignRequest(BaseModel):
    """Assign or reassign a ticket to a specific agent."""
    agent_id: int = Field(gt=0)


class TicketResolveRequest(BaseModel):
    """Close/resolve a ticket, optionally recording final notes."""
    notes: str | None = None


class TicketNoteUpdate(BaseModel):
    """Overwrite internal agent notes on a ticket."""
    notes: str = Field(min_length=1)


class AgentMessageRequest(BaseModel):
    """Human agent sends a message into an escalated conversation."""
    content: str = Field(min_length=1, max_length=4000)
