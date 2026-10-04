from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_agent_service, require_agent
from app.models.users import User
from app.schemas.agent_schema import AgentResponse, AgentStatusUpdate
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agents", tags=["Support Agents"])


@router.get("/", response_model=list[AgentResponse])
def list_agents(
    svc: AgentService = Depends(get_agent_service),
    _: User = Depends(require_agent),
):
    """List all human support agents and their current availability."""
    return svc.list_agents()


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    svc: AgentService = Depends(get_agent_service),
    _: User = Depends(require_agent),
):
    agent = svc.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}/status", response_model=AgentResponse)
def update_agent_status(
    agent_id: int,
    body: AgentStatusUpdate,
    svc: AgentService = Depends(get_agent_service),
    _: User = Depends(require_agent),
):
    """Update an agent's availability (available / busy / offline)."""
    agent = svc.update_status(agent_id, body.status)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
