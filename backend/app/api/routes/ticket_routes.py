from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_ticket_service
from app.models.support_tickets import TicketPriority, TicketStatus
from app.schemas.message_schema import MessageResponse
from app.schemas.ticket_schema import (
    AgentMessageRequest,
    TicketAssignRequest,
    TicketNoteUpdate,
    TicketResolveRequest,
    TicketResponse,
)
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


@router.get("/", response_model=list[TicketResponse])
def list_tickets(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    agent_id: int | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    svc: TicketService = Depends(get_ticket_service),
):
    """List support tickets with optional filters. Used by the agent dashboard."""
    return svc.list_tickets(
        status=status,
        priority=priority,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    svc: TicketService = Depends(get_ticket_service),
):
    ticket = svc.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.put("/{ticket_id}/assign", response_model=TicketResponse)
def assign_ticket(
    ticket_id: int,
    body: TicketAssignRequest,
    svc: TicketService = Depends(get_ticket_service),
):
    """Assign or reassign a ticket to a specific agent."""
    ticket = svc.assign_ticket(ticket_id, body.agent_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket or agent not found")
    return ticket


@router.post("/{ticket_id}/messages", response_model=MessageResponse, status_code=201)
def add_agent_message(
    ticket_id: int,
    body: AgentMessageRequest,
    agent_id: int = Query(..., description="ID of the agent sending the message"),
    svc: TicketService = Depends(get_ticket_service),
):
    """
    Human agent posts a reply into an escalated conversation.
    Advances ticket status to IN_PROGRESS on first reply.
    """
    try:
        message = svc.add_agent_message(ticket_id, agent_id, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if message is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return message


@router.put("/{ticket_id}/notes", response_model=TicketResponse)
def update_ticket_notes(
    ticket_id: int,
    body: TicketNoteUpdate,
    svc: TicketService = Depends(get_ticket_service),
):
    """Overwrite internal agent notes on a ticket."""
    ticket = svc.update_notes(ticket_id, body.notes)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/{ticket_id}/resolve", response_model=TicketResponse)
def resolve_ticket(
    ticket_id: int,
    body: TicketResolveRequest = TicketResolveRequest(),
    svc: TicketService = Depends(get_ticket_service),
):
    """
    Resolve a ticket: marks it RESOLVED, decrements agent load,
    and transitions the conversation to RESOLVED status.
    """
    ticket = svc.resolve_ticket(ticket_id, body.notes)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
