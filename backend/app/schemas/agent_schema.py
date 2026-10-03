from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.agents import AgentStatus


# ---------------------------------------------------------------------------
# LangGraph agent resume (HITL approval)
# ---------------------------------------------------------------------------

class ResumeRequest(BaseModel):
    decision: Literal["approve", "reject"]


# ---------------------------------------------------------------------------
# Human support agent management
# ---------------------------------------------------------------------------

class AgentCreateRequest(BaseModel):
    name: str
    email: str


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    status: AgentStatus
    current_ticket_count: int
    created_at: datetime


class AgentStatusUpdate(BaseModel):
    """Update a human agent's availability status."""
    status: AgentStatus
